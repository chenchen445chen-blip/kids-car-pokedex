import sqlite3
from typing import Optional
from fastapi import HTTPException

from app.db.database import normalize_text, utc_now_iso
from app.schemas import (
    BrandPatchRequest,
    InboxResolveRequest,
    ReviewActionRequest,
    SeriesPatchRequest,
    VehiclePatchRequest,
)


def _log_audit(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    action: str,
    operator: str,
    summary: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_logs (entity_type, entity_id, action, operator, summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, operator, summary, utc_now_iso()),
    )


def list_pending_brands(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM brands WHERE review_status = 'pending_review' ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def patch_brand(
    conn: sqlite3.Connection, brand_id: int, payload: BrandPatchRequest
) -> dict:
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "品牌不存在"})

    updates = payload.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE brands SET {set_clause} WHERE id = ?",
            [*updates.values(), brand_id],
        )
        _log_audit(conn, "brand", brand_id, "patch", "admin", str(list(updates.keys())))

    updated = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    return dict(updated)


def approve_brand(
    conn: sqlite3.Connection, brand_id: int, action: ReviewActionRequest
) -> dict:
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "品牌不存在"})
    if not row["name_zh"] or not row["name"]:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "审核通过品牌前必须填写规范中英文名称"},
        )

    now = utc_now_iso()
    conn.execute(
        "UPDATE brands SET review_status = 'approved', is_active = 1, updated_at = ? WHERE id = ?",
        (now, brand_id),
    )
    _log_audit(conn, "brand", brand_id, "approve", action.reviewed_by, action.review_note)
    return dict(conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone())


def list_pending_series(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.*, b.name_zh AS brand_name_zh, b.review_status AS brand_review_status
        FROM vehicle_series s
        LEFT JOIN brands b ON b.id = s.brand_id
        WHERE s.review_status = 'pending_review'
        ORDER BY s.id DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def patch_series(
    conn: sqlite3.Connection, series_id: int, payload: SeriesPatchRequest
) -> dict:
    row = conn.execute(
        "SELECT * FROM vehicle_series WHERE id = ?", (series_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车系不存在"})

    updates = payload.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = utc_now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE vehicle_series SET {set_clause} WHERE id = ?",
            [*updates.values(), series_id],
        )
        _log_audit(conn, "series", series_id, "patch", "admin", str(list(updates.keys())))

    return dict(
        conn.execute("SELECT * FROM vehicle_series WHERE id = ?", (series_id,)).fetchone()
    )


def approve_series(
    conn: sqlite3.Connection, series_id: int, action: ReviewActionRequest
) -> dict:
    row = conn.execute(
        "SELECT * FROM vehicle_series WHERE id = ?", (series_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车系不存在"})

    brand = conn.execute(
        "SELECT * FROM brands WHERE id = ? AND review_status = 'approved'",
        (row["brand_id"],),
    ).fetchone()
    if not brand:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "车系发布前必须关联已审核通过的品牌"},
        )
    if not row["name_zh"]:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "车系发布前必须具有规范中文名称"},
        )

    now = utc_now_iso()
    conn.execute(
        """
        UPDATE vehicle_series
        SET review_status = 'approved', is_active = 1, reviewed_by = ?, reviewed_at = ?, review_note = ?, updated_at = ?
        WHERE id = ?
        """,
        (action.reviewed_by, now, action.review_note, now, series_id),
    )
    _log_audit(conn, "series", series_id, "approve", action.reviewed_by, action.review_note)
    return dict(
        conn.execute("SELECT * FROM vehicle_series WHERE id = ?", (series_id,)).fetchone()
    )


def list_pending_vehicles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT v.*, b.name_zh AS brand_name_zh, s.name_zh AS series_name_zh
        FROM vehicles v
        LEFT JOIN brands b ON b.id = v.brand_id
        LEFT JOIN vehicle_series s ON s.id = v.series_id
        WHERE v.review_status = 'pending_review'
        ORDER BY v.id DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_admin_vehicle_detail(conn: sqlite3.Connection, vehicle_id: int) -> dict:
    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车型不存在"})
    cats = conn.execute(
        "SELECT category_id, is_primary FROM vehicle_category_relations WHERE vehicle_id = ?",
        (vehicle_id,),
    ).fetchall()
    rec = None
    if row["source_recognition_id"]:
        rec_row = conn.execute(
            "SELECT * FROM recognition_records WHERE id = ?",
            (row["source_recognition_id"],),
        ).fetchone()
        rec = dict(rec_row) if rec_row else None
    return {
        **dict(row),
        "category_ids": [c["category_id"] for c in cats],
        "source_recognition": rec,
    }


def patch_vehicle(
    conn: sqlite3.Connection, vehicle_id: int, payload: VehiclePatchRequest
) -> dict:
    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车型不存在"})

    data = payload.model_dump(exclude_unset=True)
    cat_ids = data.pop("category_ids", None)
    now = utc_now_iso()

    if data:
        data["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        conn.execute(
            f"UPDATE vehicles SET {set_clause} WHERE id = ?",
            [*data.values(), vehicle_id],
        )

    if cat_ids is not None:
        conn.execute(
            "DELETE FROM vehicle_category_relations WHERE vehicle_id = ?",
            (vehicle_id,),
        )
        prim_id = payload.primary_category_id or (cat_ids[0] if cat_ids else None)
        for cid in cat_ids:
            conn.execute(
                """
                INSERT INTO vehicle_category_relations (vehicle_id, category_id, is_primary, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (vehicle_id, cid, 1 if cid == prim_id else 0, now),
            )

    _log_audit(conn, "vehicle", vehicle_id, "patch", "admin", "更新待审核车型资料")
    return get_admin_vehicle_detail(conn, vehicle_id)


def approve_vehicle(
    conn: sqlite3.Connection, vehicle_id: int, action: ReviewActionRequest
) -> dict:
    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车型不存在"})

    # 校验审核通过条件：品牌已审核、车系已审核、车型名规范、有至少一个有效分类、有儿童版介绍
    if not row["brand_id"] or not row["series_id"]:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "具体车型审核通过前必须关联品牌与所属车系"},
        )
    brand_ok = conn.execute(
        "SELECT 1 FROM brands WHERE id = ? AND review_status = 'approved'",
        (row["brand_id"],),
    ).fetchone()
    series_ok = conn.execute(
        "SELECT 1 FROM vehicle_series WHERE id = ? AND review_status = 'approved'",
        (row["series_id"],),
    ).fetchone()
    if not brand_ok or not series_ok:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "所属品牌或车系尚未审核通过，请先审核上级品牌与车系"},
        )

    if not row["model_name"] or not row["introduction_child"]:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "审核通过前必须补全规范车型名称与儿童版知识介绍 (introduction_child)"},
        )

    cat_cnt = conn.execute(
        "SELECT COUNT(1) AS cnt FROM vehicle_category_relations WHERE vehicle_id = ?",
        (vehicle_id,),
    ).fetchone()
    if not cat_cnt or int(cat_cnt["cnt"]) == 0:
        raise HTTPException(
            status_code=422,
            detail={"code": 42201, "message": "审核通过前必须为车型分配至少一个有效的车辆类型分类"},
        )

    now = utc_now_iso()
    conn.execute(
        """
        UPDATE vehicles
        SET review_status = 'approved', is_active = 1, reviewed_by = ?, reviewed_at = ?, review_note = ?, updated_at = ?
        WHERE id = ?
        """,
        (action.reviewed_by, now, action.review_note, now, vehicle_id),
    )
    _log_audit(conn, "vehicle", vehicle_id, "approve", action.reviewed_by, action.review_note)
    return get_admin_vehicle_detail(conn, vehicle_id)


def reject_vehicle(
    conn: sqlite3.Connection, vehicle_id: int, action: ReviewActionRequest
) -> dict:
    row = conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "车型不存在"})

    now = utc_now_iso()
    conn.execute(
        """
        UPDATE vehicles
        SET review_status = 'rejected', is_active = 0, reviewed_by = ?, reviewed_at = ?, review_note = ?, updated_at = ?
        WHERE id = ?
        """,
        (action.reviewed_by, now, action.review_note, now, vehicle_id),
    )
    _log_audit(conn, "vehicle", vehicle_id, "reject", action.reviewed_by, action.review_note)
    return get_admin_vehicle_detail(conn, vehicle_id)


def list_recognition_inbox(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM recognition_inbox WHERE status = 'pending' ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_recognition_inbox(
    conn: sqlite3.Connection, inbox_id: int, payload: InboxResolveRequest
) -> dict:
    row = conn.execute(
        "SELECT * FROM recognition_inbox WHERE id = ?", (inbox_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": 40401, "message": "待处理记录不存在"})

    now = utc_now_iso()
    if payload.action == "ignore":
        conn.execute(
            "UPDATE recognition_inbox SET status = 'ignored', updated_at = ? WHERE id = ?",
            (now, inbox_id),
        )
    elif payload.action == "link_existing":
        conn.execute(
            """
            UPDATE recognition_inbox
            SET status = 'resolved', resolved_brand_id = ?, resolved_series_id = ?, resolved_vehicle_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.resolved_brand_id,
                payload.resolved_series_id,
                payload.resolved_vehicle_id,
                now,
                inbox_id,
            ),
        )
    elif payload.action == "create_draft":
        if not payload.model_name:
            raise HTTPException(
                status_code=422,
                detail={"code": 42201, "message": "转为新车型草稿时必须提供 model_name"},
            )
        dedupe = normalize_text(f"{payload.brand_name_zh}_{payload.series_name_zh}_{payload.model_name}")
        cur = conn.execute(
            """
            INSERT INTO vehicles (
                brand_id, series_id, brand_name_raw, series_name_raw,
                primary_category_id, model_name, model_name_zh, source_type,
                dedupe_key, review_status, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ai_recognition', ?, 'pending_review', 1, ?, ?)
            """,
            (
                payload.resolved_brand_id,
                payload.resolved_series_id,
                payload.brand_name_zh,
                payload.series_name_zh,
                payload.primary_category_id,
                payload.model_name,
                payload.model_name,
                dedupe,
                now,
                now,
            ),
        )
        new_vid = int(cur.lastrowid)
        conn.execute(
            """
            UPDATE recognition_inbox
            SET status = 'resolved', resolved_vehicle_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_vid, now, inbox_id),
        )

    _log_audit(conn, "recognition_inbox", inbox_id, payload.action, "admin")
    return dict(
        conn.execute("SELECT * FROM recognition_inbox WHERE id = ?", (inbox_id,)).fetchone()
    )

