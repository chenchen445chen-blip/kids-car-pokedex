import sqlite3
from typing import Optional

from app.db.database import normalize_text
from app.services.image_service import build_image_url, resolve_preferred_image_url


BRAND_GROUP_LABELS = {
    "china_independent": "中国自主品牌",
    "china_nev": "中国新能源及新势力",
    "joint_venture": "合资及国际常见品牌",
    "luxury_import": "豪华及进口常见品牌",
    "construction_machinery": "商用车及工程机械品牌",
}


def list_brands(
    conn: sqlite3.Connection,
    keyword: Optional[str] = None,
    brand_group: Optional[str] = None,
    parent_brand_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    conditions = ["b.review_status = 'approved'", "b.is_active = 1"]
    params: list = []

    if brand_group:
        conditions.append("b.brand_group = ?")
        params.append(brand_group)

    if parent_brand_id is not None:
        conditions.append("b.parent_brand_id = ?")
        params.append(parent_brand_id)

    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        norm_kw = f"%{normalize_text(keyword)}%"
        conditions.append(
            """
            (
                b.name LIKE ?
                OR b.name_zh LIKE ?
                OR EXISTS (
                    SELECT 1 FROM brand_aliases ba
                    WHERE ba.brand_id = b.id
                      AND ba.review_status = 'approved'
                      AND (ba.alias LIKE ? OR ba.normalized_alias LIKE ?)
                )
            )
            """
        )
        params.extend([kw, kw, kw, norm_kw])

    where_sql = " AND ".join(conditions)
    offset = max(0, (page - 1) * page_size)

    total_row = conn.execute(
        f"SELECT COUNT(1) AS cnt FROM brands b WHERE {where_sql}", params
    ).fetchone()
    total = int(total_row["cnt"]) if total_row else 0

    rows = conn.execute(
        f"""
        SELECT
            b.id,
            b.parent_brand_id,
            b.name,
            b.name_zh,
            b.brand_group,
            b.country,
            b.logo_image_id,
            b.slogan_child,
            b.introduction_child,
            b.sort_order,
            (
                SELECT COUNT(1) FROM vehicle_series s
                WHERE s.brand_id = b.id
                  AND s.series_type = 'vehicle_series'
                  AND s.review_status = 'approved'
                  AND s.is_active = 1
            ) AS series_count,
            (
                SELECT COUNT(1) FROM vehicles v
                WHERE v.brand_id = b.id
                  AND v.review_status = 'approved'
                  AND v.is_active = 1
            ) AS vehicle_count
        FROM brands b
        WHERE {where_sql}
        ORDER BY b.sort_order ASC, b.id ASC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()

    items = [
        {
            "id": r["id"],
            "parent_brand_id": r["parent_brand_id"],
            "name": r["name"],
            "name_zh": r["name_zh"],
            "brand_group": r["brand_group"],
            "brand_group_label": BRAND_GROUP_LABELS.get(r["brand_group"], "其他品牌"),
            "country": r["country"],
            "logo_url": resolve_preferred_image_url(conn, r["logo_image_id"]),
            "slogan_child": r["slogan_child"] or "真实汽车认知图鉴",
            "introduction_child": r["introduction_child"],
            "series_count": r["series_count"],
            "vehicle_count": r["vehicle_count"],
            "sort_order": r["sort_order"],
        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_brand_detail(conn: sqlite3.Connection, brand_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT
            b.id,
            b.parent_brand_id,
            b.name,
            b.name_zh,
            b.brand_group,
            b.country,
            b.logo_image_id,
            b.slogan_child,
            b.introduction_child
        FROM brands b
        WHERE b.id = ? AND b.review_status = 'approved' AND b.is_active = 1
        """,
        (brand_id,),
    ).fetchone()
    if not row:
        return None

    sub_brands = conn.execute(
        """
        SELECT id, name, name_zh, logo_image_id
        FROM brands
        WHERE parent_brand_id = ? AND review_status = 'approved' AND is_active = 1
        ORDER BY sort_order ASC, id ASC
        """,
        (brand_id,),
    ).fetchall()

    series_data = list_brand_series(conn, brand_id=brand_id)

    return {
        "id": row["id"],
        "parent_brand_id": row["parent_brand_id"],
        "name": row["name"],
        "name_zh": row["name_zh"],
        "brand_group": row["brand_group"],
        "brand_group_label": BRAND_GROUP_LABELS.get(row["brand_group"], "其他品牌"),
        "country": row["country"],
        "logo_url": resolve_preferred_image_url(conn, row["logo_image_id"]),
        "slogan_child": row["slogan_child"] or "豪华 · 品质 · 未来",
        "introduction_child": row["introduction_child"],
        "sub_brands": [
            {
                "id": sb["id"],
                "name": sb["name"],
                "name_zh": sb["name_zh"],
                "logo_url": resolve_preferred_image_url(conn, sb["logo_image_id"]),
            }
            for sb in sub_brands
        ],
        "series_count": len(series_data["items"]),
        "product_lines": series_data["product_lines"],
        "series_list": series_data["items"],
    }


def list_brand_series(
    conn: sqlite3.Connection,
    brand_id: int,
    parent_series_id: Optional[int] = None,
    keyword: Optional[str] = None,
) -> dict:
    conditions = [
        "s.brand_id = ?",
        "s.review_status = 'approved'",
        "s.is_active = 1",
    ]
    params: list = [brand_id]

    if parent_series_id is not None:
        conditions.append("s.parent_series_id = ?")
        params.append(parent_series_id)

    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        norm_kw = f"%{normalize_text(keyword)}%"
        conditions.append(
            """
            (
                s.name LIKE ?
                OR s.name_zh LIKE ?
                OR EXISTS (
                    SELECT 1 FROM vehicle_series_aliases sa
                    WHERE sa.series_id = s.id
                      AND sa.review_status = 'approved'
                      AND (sa.alias LIKE ? OR sa.normalized_alias LIKE ?)
                )
            )
            """
        )
        params.extend([kw, kw, kw, norm_kw])

    rows = conn.execute(
        f"""
        SELECT
            s.id,
            s.brand_id,
            s.parent_series_id,
            s.code,
            s.name,
            s.name_zh,
            s.series_type,
            s.body_type_label,
            s.introduction_child,
            s.cover_image_id,
            s.sort_order,
            (
                SELECT COUNT(1) FROM vehicles v
                WHERE v.series_id = s.id
                  AND v.review_status = 'approved'
                  AND v.is_active = 1
            ) AS vehicle_count
        FROM vehicle_series s
        WHERE {' AND '.join(conditions)}
        ORDER BY s.sort_order ASC, s.id ASC
        """,
        params,
    ).fetchall()

    product_lines: list[dict] = []
    vehicle_series_items: list[dict] = []

    for r in rows:
        item = {
            "id": r["id"],
            "brand_id": r["brand_id"],
            "parent_series_id": r["parent_series_id"],
            "code": r["code"],
            "name": r["name"],
            "name_zh": r["name_zh"],
            "series_type": r["series_type"],
            "body_type_label": r["body_type_label"] or "常见车系",
            "introduction_child": r["introduction_child"],
            "cover_image_url": resolve_preferred_image_url(conn, r["cover_image_id"]),
            "vehicle_count": r["vehicle_count"],
            "sort_order": r["sort_order"],
        }
        if r["series_type"] == "product_line":
            product_lines.append({**item, "series": []})
        else:
            vehicle_series_items.append(item)

    pl_by_id = {pl["id"]: pl for pl in product_lines}
    for vs in vehicle_series_items:
        pid = vs["parent_series_id"]
        if pid and pid in pl_by_id:
            pl_by_id[pid]["series"].append(vs)

    return {
        "product_lines": product_lines,
        "items": vehicle_series_items,
    }

