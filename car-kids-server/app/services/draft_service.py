import json
import sqlite3
from typing import Optional

from app.core.config import settings
from app.db.database import normalize_text, utc_now_iso
from app.services.catalog_service import get_vehicle_detail
from app.services.matching_service import (
    match_brand,
    match_category_by_name,
    match_series,
    match_vehicle_under_series,
)
from app.services.series_service import get_series_detail


def process_recognition_result(
    conn: sqlite3.Connection,
    request_id: str,
    provider_result: dict,
) -> dict:
    """
    核心识别分层匹配与自动入库引擎（遵循需求文档 3.3.2 - 3.3.5 与 7.3）：
    1. 幂等校验：若 request_id 已存在，直接返回之前的识别结果，避免重复入库。
    2. 按 品牌 -> 产品线/车系 -> 具体车型 逐级匹配本地已审核数据。
    3. 精确命中具体车型 -> 返回 matched (level='vehicle')。
    4. 只命中车系（AI 未提供可靠具体车型名）-> 返回 matched (level='series')，绝不随机挑选具体配置。
    5. 多候选歧义 -> 返回 candidates。
    6. 本地未命中且信息足够 -> 创建对应层级的 pending_review 草稿。
    7. 信息不足或置信度过低 -> 写入 recognition_inbox，返回 unrecognized。
    """
    existing_rec = conn.execute(
        "SELECT * FROM recognition_records WHERE request_id = ?", (request_id,)
    ).fetchone()
    if existing_rec:
        return _build_response_from_existing_record(conn, existing_rec)

    provider_name = provider_result.get("provider") or settings.RECOGNITION_PROVIDER
    candidates = provider_result.get("candidates") or []
    raw_json = json.dumps(provider_result, ensure_ascii=False)
    now = utc_now_iso()

    if not candidates:
        return _save_unrecognized(
            conn,
            request_id=request_id,
            provider_name=provider_name,
            raw_json=raw_json,
            reason="第三方识别未返回任何候选",
            confidence=0.0,
            now=now,
        )

    top = candidates[0]
    confidence = float(top.get("confidence") or 0.0)
    brand_en = top.get("brand_name")
    brand_zh = top.get("brand_name_zh")
    series_en = top.get("series_name")
    series_zh = top.get("series_name_zh")
    model_name = top.get("model_name")
    trim_name = top.get("trim_name")
    model_year = top.get("model_year")
    raw_cat = top.get("vehicle_category")

    # 置信度过低或既无品牌也无车系/车型名称 -> 保存到 recognition_inbox
    if confidence < settings.CANDIDATE_CONFIDENCE_THRESHOLD or (
        not (brand_zh or brand_en) and not (series_zh or series_en or model_name)
    ):
        return _save_unrecognized(
            conn,
            request_id=request_id,
            provider_name=provider_name,
            raw_json=raw_json,
            reason="识别置信度低于阈值或缺少可信品牌/车系信息",
            confidence=confidence,
            now=now,
        )

    matched_brand = match_brand(conn, brand_en, brand_zh)
    matched_brand_id = int(matched_brand["id"]) if matched_brand else None

    # 只有品牌，没有车系且没有具体车型名称 -> 信息不足，写 inbox
    if not (series_zh or series_en) and not model_name:
        return _save_unrecognized(
            conn,
            request_id=request_id,
            provider_name=provider_name,
            raw_json=raw_json,
            reason="仅识别到品牌或车辆大类，缺少车系或具体车型名称",
            confidence=confidence,
            now=now,
        )

    # 若品牌已匹配，继续匹配车系
    if matched_brand_id:
        series_matches = match_series(conn, matched_brand_id, series_en, series_zh)

        if len(series_matches) == 1:
            matched_series_row = series_matches[0]
            s_id = int(matched_series_row["id"])

            # 如果 AI 同时提供了具体车型名，尝试第 3 级具体车型匹配
            if model_name and model_name.strip():
                vehicle_matches = match_vehicle_under_series(
                    conn, s_id, model_name, trim_name, model_year
                )
                if len(vehicle_matches) == 1:
                    v_id = int(vehicle_matches[0]["id"])
                    rec_id = _insert_recognition_record(
                        conn,
                        request_id=request_id,
                        provider_name=provider_name,
                        result_status="matched",
                        matched_brand_id=matched_brand_id,
                        matched_series_id=s_id,
                        matched_vehicle_id=v_id,
                        confidence=confidence,
                        raw_json=raw_json,
                        now=now,
                    )
                    _insert_candidates(conn, rec_id, candidates, matched_brand_id, s_id, v_id)
                    v_detail = get_vehicle_detail(conn, v_id)
                    return {
                        "status": "matched",
                        "match_level": "vehicle",
                        "vehicle": _format_matched_vehicle(v_detail),
                        "series": get_series_detail(conn, s_id),
                    }
                elif len(vehicle_matches) > 1:
                    return _save_multiple_candidates(
                        conn,
                        request_id=request_id,
                        provider_name=provider_name,
                        vehicle_rows=vehicle_matches,
                        confidence=confidence,
                        raw_json=raw_json,
                        now=now,
                    )
                else:
                    # 品牌与车系均已存在，但具体车型未收录 -> 自动创建具体车型待审核草稿
                    return _create_pending_draft(
                        conn,
                        request_id=request_id,
                        provider_name=provider_name,
                        brand_id=matched_brand_id,
                        brand_raw=brand_zh or brand_en,
                        series_id=s_id,
                        series_raw=series_zh or series_en,
                        model_name=model_name,
                        trim_name=trim_name,
                        model_year=model_year,
                        raw_category=raw_cat,
                        confidence=confidence,
                        raw_json=raw_json,
                        now=now,
                    )
            else:
                # AI 仅识别到车系（如“奔驰 E 级”），直接返回已审核车系详情，绝不随机下推到 E 260 L / E 300 L
                rec_id = _insert_recognition_record(
                    conn,
                    request_id=request_id,
                    provider_name=provider_name,
                    result_status="matched",
                    matched_brand_id=matched_brand_id,
                    matched_series_id=s_id,
                    matched_vehicle_id=None,
                    confidence=confidence,
                    raw_json=raw_json,
                    now=now,
                )
                _insert_candidates(conn, rec_id, candidates, matched_brand_id, s_id, None)
                s_detail = get_series_detail(conn, s_id)
                return {
                    "status": "matched",
                    "match_level": "series",
                    "series": s_detail,
                    "vehicle": _format_series_as_vehicle_card(s_detail),
                }

        elif len(series_matches) > 1:
            # 同一品牌下命中多个相似车系
            v_rows = conn.execute(
                f"""
                SELECT * FROM vehicles
                WHERE series_id IN ({','.join('?' for _ in series_matches)})
                  AND review_status = 'approved' AND is_active = 1
                LIMIT 5
                """,
                [r["id"] for r in series_matches],
            ).fetchall()
            return _save_multiple_candidates(
                conn,
                request_id=request_id,
                provider_name=provider_name,
                vehicle_rows=v_rows,
                confidence=confidence,
                raw_json=raw_json,
                now=now,
            )

    # 品牌未收录 或 品牌已存在但车系未收录 -> 创建对应层级的 pending_review 草稿
    return _create_pending_draft(
        conn,
        request_id=request_id,
        provider_name=provider_name,
        brand_id=matched_brand_id,
        brand_raw=brand_zh or brand_en,
        series_id=None,
        series_raw=series_zh or series_en,
        model_name=model_name,
        trim_name=trim_name,
        model_year=model_year,
        raw_category=raw_cat,
        confidence=confidence,
        raw_json=raw_json,
        now=now,
    )


def _format_matched_vehicle(v_detail: Optional[dict]) -> dict:
    if not v_detail:
        return {}
    return {
        "id": v_detail["id"],
        "brand_id": v_detail["brand"]["id"],
        "brand_name": v_detail["brand"]["name_zh"],
        "brand_logo_url": v_detail["brand"]["logo_url"],
        "series_id": v_detail["series"]["id"] if v_detail.get("series") else None,
        "series_name": v_detail["series"]["name_zh"] if v_detail.get("series") else None,
        "model_name": v_detail["model_name_zh"] or v_detail["model_name"],
        "model_year": v_detail["model_year"],
        "categories": v_detail["category_names"],
        "cover_image_url": v_detail["cover_image_url"],
        "cover_image_type": v_detail["cover_image_type"],
        "introduction_child": v_detail["introduction_child"],
    }


def _format_series_as_vehicle_card(s_detail: Optional[dict]) -> dict:
    if not s_detail:
        return {}
    return {
        "id": None,
        "brand_id": s_detail["brand"]["id"],
        "brand_name": s_detail["brand"]["name_zh"],
        "brand_logo_url": s_detail["brand"]["logo_url"],
        "series_id": s_detail["id"],
        "series_name": s_detail["name_zh"],
        "model_name": f"{s_detail['brand']['name_zh']} {s_detail['name_zh']}",
        "categories": [s_detail.get("body_type_label") or "家用车"],
        "cover_image_url": s_detail["cover_image_url"],
        "cover_image_type": "real_photo",
        "introduction_child": s_detail["introduction_child"],
    }


def _insert_recognition_record(
    conn: sqlite3.Connection,
    request_id: str,
    provider_name: str,
    result_status: str,
    matched_brand_id: Optional[int] = None,
    matched_series_id: Optional[int] = None,
    matched_vehicle_id: Optional[int] = None,
    created_brand_id: Optional[int] = None,
    created_series_id: Optional[int] = None,
    created_vehicle_id: Optional[int] = None,
    confidence: Optional[float] = None,
    raw_json: Optional[str] = None,
    now: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO recognition_records (
            request_id, provider_name, result_status,
            matched_brand_id, matched_series_id, matched_vehicle_id,
            created_brand_id, created_series_id, created_vehicle_id,
            confidence, raw_result_json, image_retained, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            request_id,
            provider_name,
            result_status,
            matched_brand_id,
            matched_series_id,
            matched_vehicle_id,
            created_brand_id,
            created_series_id,
            created_vehicle_id,
            confidence,
            raw_json,
            now or utc_now_iso(),
        ),
    )
    return int(cur.lastrowid)


def _insert_candidates(
    conn: sqlite3.Connection,
    rec_id: int,
    candidates: list[dict],
    brand_id: Optional[int],
    series_id: Optional[int],
    vehicle_id: Optional[int],
) -> None:
    for idx, c in enumerate(candidates, start=1):
        conn.execute(
            """
            INSERT INTO recognition_candidates (
                recognition_record_id, brand_id, series_id, vehicle_id,
                raw_brand_name, raw_series_name, raw_model_name, raw_category_name,
                confidence, rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec_id,
                brand_id if idx == 1 else None,
                series_id if idx == 1 else None,
                vehicle_id if idx == 1 else None,
                c.get("brand_name_zh") or c.get("brand_name"),
                c.get("series_name_zh") or c.get("series_name"),
                c.get("model_name"),
                c.get("vehicle_category"),
                c.get("confidence"),
                idx,
            ),
        )


def _create_pending_draft(
    conn: sqlite3.Connection,
    request_id: str,
    provider_name: str,
    brand_id: Optional[int],
    brand_raw: Optional[str],
    series_id: Optional[int],
    series_raw: Optional[str],
    model_name: Optional[str],
    trim_name: Optional[str],
    model_year: Optional[int],
    raw_category: Optional[str],
    confidence: float,
    raw_json: str,
    now: str,
) -> dict:
    created_brand_id: Optional[int] = None
    created_series_id: Optional[int] = None
    created_vehicle_id: Optional[int] = None

    # 1. 如品牌未收录但有品牌名，创建或复用待审核品牌
    if not brand_id and brand_raw:
        existing_b = conn.execute(
            "SELECT id FROM brands WHERE name_zh = ? OR name = ? LIMIT 1",
            (brand_raw, brand_raw),
        ).fetchone()
        if existing_b:
            brand_id = int(existing_b["id"])
        else:
            cur_b = conn.execute(
                """
                INSERT INTO brands (
                    name, name_zh, brand_group, review_status, is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, 'china_independent', 'pending_review', 1, 999, ?, ?)
                """,
                (brand_raw, brand_raw, now, now),
            )
            brand_id = int(cur_b.lastrowid)
            created_brand_id = brand_id

    # 2. 如车系未收录但有车系名且关联到品牌，创建或复用待审核车系
    if brand_id and not series_id and series_raw:
        existing_s = conn.execute(
            "SELECT id FROM vehicle_series WHERE brand_id = ? AND (name_zh = ? OR name = ?) LIMIT 1",
            (brand_id, series_raw, series_raw),
        ).fetchone()
        if existing_s:
            series_id = int(existing_s["id"])
        else:
            cur_s = conn.execute(
                """
                INSERT INTO vehicle_series (
                    brand_id, name, name_zh, series_type, review_status, is_active,
                    sort_order, source_type, source_provider, created_at, updated_at
                ) VALUES (?, ?, ?, 'vehicle_series', 'pending_review', 1, 999, 'ai_recognition', ?, ?, ?)
                """,
                (brand_id, series_raw, series_raw, provider_name, now, now),
            )
            series_id = int(cur_s.lastrowid)
            created_series_id = series_id

    # 3. 如有具体车型名，创建或复用待审核具体车型（使用 dedupe_key 防止并发重复）
    if model_name and model_name.strip():
        dedupe = normalize_text(
            f"{brand_raw or brand_id}_{series_raw or series_id}_{model_name}_{model_year or ''}_{trim_name or ''}"
        )
        existing_v = conn.execute(
            "SELECT id FROM vehicles WHERE dedupe_key = ? LIMIT 1", (dedupe,)
        ).fetchone()
        if existing_v:
            created_vehicle_id = int(existing_v["id"])
        else:
            prim_cat_id = match_category_by_name(conn, raw_category)
            cur_v = conn.execute(
                """
                INSERT INTO vehicles (
                    brand_id, series_id, brand_name_raw, series_name_raw,
                    primary_category_id, model_name, model_name_zh, trim_name, model_year,
                    body_style, source_type, source_provider, recognition_confidence,
                    dedupe_key, review_status, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_recognition', ?, ?, ?, 'pending_review', 1, ?, ?)
                """,
                (
                    brand_id,
                    series_id,
                    brand_raw,
                    series_raw,
                    prim_cat_id,
                    model_name.strip(),
                    model_name.strip(),
                    trim_name,
                    model_year,
                    raw_category,
                    provider_name,
                    confidence,
                    dedupe,
                    now,
                    now,
                ),
            )
            created_vehicle_id = int(cur_v.lastrowid)
            if prim_cat_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO vehicle_category_relations (vehicle_id, category_id, is_primary, created_at)
                    VALUES (?, ?, 1, ?)
                    """,
                    (created_vehicle_id, prim_cat_id, now),
                )

    rec_id = _insert_recognition_record(
        conn,
        request_id=request_id,
        provider_name=provider_name,
        result_status="pending_review",
        matched_brand_id=brand_id if not created_brand_id else None,
        matched_series_id=series_id if not created_series_id else None,
        created_brand_id=created_brand_id,
        created_series_id=created_series_id,
        created_vehicle_id=created_vehicle_id,
        confidence=confidence,
        raw_json=raw_json,
        now=now,
    )

    if created_vehicle_id:
        conn.execute(
            "UPDATE vehicles SET source_recognition_id = ? WHERE id = ?",
            (rec_id, created_vehicle_id),
        )

    return {
        "status": "pending_review",
        "pending_vehicle_id": created_vehicle_id,
        "pending_series_id": created_series_id,
        "pending_brand_id": created_brand_id,
        "child_message": "发现一辆新车，资料正在整理。",
    }


def _save_multiple_candidates(
    conn: sqlite3.Connection,
    request_id: str,
    provider_name: str,
    vehicle_rows: list[sqlite3.Row],
    confidence: float,
    raw_json: str,
    now: str,
) -> dict:
    from app.services.image_service import get_primary_vehicle_image

    _insert_recognition_record(
        conn,
        request_id=request_id,
        provider_name=provider_name,
        result_status="candidates",
        confidence=confidence,
        raw_json=raw_json,
        now=now,
    )
    cand_list = []
    for vr in vehicle_rows:
        img = get_primary_vehicle_image(conn, vr["id"])
        cand_list.append(
            {
                "vehicle_id": vr["id"],
                "model_name": vr["model_name_zh"] or vr["model_name"],
                "cover_image_url": img["cover_image_url"],
            }
        )
    return {
        "status": "candidates",
        "candidates": cand_list,
        "child_message": "看起来可能是这些车，请和家长一起确认。",
    }


def _save_unrecognized(
    conn: sqlite3.Connection,
    request_id: str,
    provider_name: str,
    raw_json: str,
    reason: str,
    confidence: float,
    now: str,
) -> dict:
    rec_id = _insert_recognition_record(
        conn,
        request_id=request_id,
        provider_name=provider_name,
        result_status="unrecognized",
        confidence=confidence,
        raw_json=raw_json,
        now=now,
    )
    conn.execute(
        """
        INSERT INTO recognition_inbox (
            recognition_record_id, raw_result_json, reason, status, created_at, updated_at
        ) VALUES (?, ?, ?, 'pending', ?, ?)
        """,
        (rec_id, raw_json, reason, now, now),
    )
    return {
        "status": "unrecognized",
        "child_message": "这辆车还不认识，我们换个角度再拍一次吧。",
    }


def _build_response_from_existing_record(
    conn: sqlite3.Connection, rec: sqlite3.Row
) -> dict:
    status = rec["result_status"]
    if status == "matched":
        if rec["matched_vehicle_id"]:
            v_detail = get_vehicle_detail(conn, int(rec["matched_vehicle_id"]))
            return {
                "status": "matched",
                "match_level": "vehicle",
                "vehicle": _format_matched_vehicle(v_detail),
                "series": (
                    get_series_detail(conn, int(rec["matched_series_id"]))
                    if rec["matched_series_id"]
                    else None
                ),
            }
        if rec["matched_series_id"]:
            s_detail = get_series_detail(conn, int(rec["matched_series_id"]))
            return {
                "status": "matched",
                "match_level": "series",
                "series": s_detail,
                "vehicle": _format_series_as_vehicle_card(s_detail),
            }
    if status == "pending_review":
        return {
            "status": "pending_review",
            "pending_vehicle_id": rec["created_vehicle_id"],
            "pending_series_id": rec["created_series_id"],
            "pending_brand_id": rec["created_brand_id"],
            "child_message": "发现一辆新车，资料正在整理。",
        }
    return {
        "status": status,
        "child_message": "这辆车还不认识，我们换个角度再拍一次吧。",
    }

