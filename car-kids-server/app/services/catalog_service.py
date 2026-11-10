import sqlite3
from typing import Optional

from app.db.database import normalize_text
from app.services.image_service import (
    build_image_url,
    get_primary_vehicle_image,
    get_vehicle_gallery,
    resolve_preferred_image_url,
)


def _get_vehicle_categories(conn: sqlite3.Connection, vehicle_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.id, c.code, c.name, vcr.is_primary
        FROM vehicle_category_relations vcr
        JOIN vehicle_categories c ON c.id = vcr.category_id
        WHERE vcr.vehicle_id = ? AND c.is_active = 1
        ORDER BY vcr.is_primary DESC, c.sort_order ASC
        """,
        (vehicle_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "is_primary": bool(r["is_primary"]),
        }
        for r in rows
    ]


def list_vehicles(
    conn: sqlite3.Connection,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    series_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    conditions = ["v.review_status = 'approved'", "v.is_active = 1"]
    params: list = []

    if category_id is not None:
        # 同时包含该分类及其直接子分类下的已审核车型
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM vehicle_category_relations vcr
                JOIN vehicle_categories c ON c.id = vcr.category_id
                WHERE vcr.vehicle_id = v.id
                  AND (c.id = ? OR c.parent_id = ?)
            )
            """
        )
        params.extend([category_id, category_id])

    if brand_id is not None:
        conditions.append("v.brand_id = ?")
        params.append(brand_id)

    if series_id is not None:
        conditions.append("v.series_id = ?")
        params.append(series_id)

    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        norm_kw = f"%{normalize_text(keyword)}%"
        conditions.append(
            """
            (
                v.model_name LIKE ?
                OR v.model_name_zh LIKE ?
                OR b.name LIKE ?
                OR b.name_zh LIKE ?
                OR s.name_zh LIKE ?
                OR EXISTS (
                    SELECT 1 FROM vehicle_aliases va
                    WHERE va.vehicle_id = v.id
                      AND va.review_status = 'approved'
                      AND (va.alias LIKE ? OR va.normalized_alias LIKE ?)
                )
            )
            """
        )
        params.extend([kw, kw, kw, kw, kw, kw, norm_kw])

    where_sql = " AND ".join(conditions)
    offset = max(0, (page - 1) * page_size)

    total_row = conn.execute(
        f"""
        SELECT COUNT(1) AS cnt
        FROM vehicles v
        LEFT JOIN brands b ON b.id = v.brand_id
        LEFT JOIN vehicle_series s ON s.id = v.series_id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()
    total = int(total_row["cnt"]) if total_row else 0

    rows = conn.execute(
        f"""
        SELECT
            v.id,
            v.brand_id,
            v.series_id,
            v.primary_category_id,
            v.model_name,
            v.model_name_zh,
            v.trim_name,
            v.model_year,
            v.body_style,
            v.power_type,
            v.introduction_child,
            b.name AS brand_name,
            b.name_zh AS brand_name_zh,
            b.logo_image_id AS brand_logo_id,
            s.name_zh AS series_name_zh
        FROM vehicles v
        LEFT JOIN brands b ON b.id = v.brand_id
        LEFT JOIN vehicle_series s ON s.id = v.series_id
        WHERE {where_sql}
        ORDER BY v.id ASC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()

    items = []
    for r in rows:
        cats = _get_vehicle_categories(conn, r["id"])
        img_info = get_primary_vehicle_image(conn, r["id"])
        primary_cat = cats[0] if cats else None
        items.append(
            {
                "id": r["id"],
                "brand": {
                    "id": r["brand_id"],
                    "name": r["brand_name"],
                    "name_zh": r["brand_name_zh"],
                    "logo_url": resolve_preferred_image_url(conn, r["brand_logo_id"]),
                },
                "series": (
                    {"id": r["series_id"], "name_zh": r["series_name_zh"]}
                    if r["series_id"]
                    else None
                ),
                "model_name": r["model_name"],
                "model_name_zh": r["model_name_zh"] or r["model_name"],
                "trim_name": r["trim_name"],
                "model_year": r["model_year"],
                "body_style": r["body_style"],
                "power_type": r["power_type"],
                "introduction_child": r["introduction_child"],
                "category_ids": [c["id"] for c in cats],
                "categories": [c["name"] for c in cats],
                "primary_category": primary_cat,
                **img_info,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_random_vehicles(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> dict:
    """随机抽取已审核车型列表（附带完整大图列表与宽高信息，供抖音式上下滑整页浏览使用）。"""
    rows = conn.execute(
        """
        SELECT
            v.id,
            v.brand_id,
            v.series_id,
            v.primary_category_id,
            v.model_name,
            v.model_name_zh,
            v.trim_name,
            v.model_year,
            v.body_style,
            v.power_type,
            v.introduction_child,
            v.recognition_features,
            b.name AS brand_name,
            b.name_zh AS brand_name_zh,
            b.logo_image_id AS brand_logo_id,
            s.name_zh AS series_name_zh,
            s.body_type_label AS series_body_label
        FROM vehicles v
        LEFT JOIN brands b ON b.id = v.brand_id
        LEFT JOIN vehicle_series s ON s.id = v.series_id
        WHERE v.review_status = 'approved'
          AND v.is_active = 1
        ORDER BY RANDOM()
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    items = []
    for r in rows:
        cats = _get_vehicle_categories(conn, r["id"])
        img_info = get_primary_vehicle_image(conn, r["id"])
        gallery = get_vehicle_gallery(conn, r["id"])
        primary_cat = cats[0] if cats else None
        items.append(
            {
                "id": r["id"],
                "brand_id": r["brand_id"],
                "brand_name": r["brand_name"],
                "brand_name_zh": r["brand_name_zh"] or "",
                "brand": {
                    "id": r["brand_id"],
                    "name": r["brand_name"],
                    "name_zh": r["brand_name_zh"],
                    "logo_url": resolve_preferred_image_url(conn, r["brand_logo_id"]),
                },
                "series_id": r["series_id"],
                "series_name_zh": r["series_name_zh"] or "",
                "series": (
                    {"id": r["series_id"], "name_zh": r["series_name_zh"]}
                    if r["series_id"]
                    else None
                ),
                "model_name": r["model_name"],
                "model_name_zh": r["model_name_zh"] or r["model_name"],
                "trim_name": r["trim_name"] or "",
                "model_year": r["model_year"] or 2024,
                "body_style": r["body_style"] or r["series_body_label"] or "汽车",
                "power_type": r["power_type"] or "",
                "introduction_child": r["introduction_child"] or "",
                "recognition_features": r["recognition_features"] or "",
                "category_ids": [c["id"] for c in cats],
                "categories": [c["name"] for c in cats],
                "category_label": " · ".join([c["name"] for c in cats]) if cats else "常见汽车",
                "primary_category": primary_cat,
                **img_info,
                "images": gallery,
            }
        )

    return {
        "items": items,
        "total": len(items),
    }


def get_vehicle_detail(conn: sqlite3.Connection, vehicle_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT
            v.id,
            v.brand_id,
            v.series_id,
            v.primary_category_id,
            v.model_name,
            v.model_name_zh,
            v.trim_name,
            v.generation,
            v.model_year,
            v.body_style,
            v.power_type,
            v.introduction_child,
            v.introduction_parent,
            v.recognition_features,
            v.usage_description,
            b.name AS brand_name,
            b.name_zh AS brand_name_zh,
            b.country AS brand_country,
            b.logo_image_id AS brand_logo_id,
            s.name AS series_name,
            s.name_zh AS series_name_zh
        FROM vehicles v
        LEFT JOIN brands b ON b.id = v.brand_id
        LEFT JOIN vehicle_series s ON s.id = v.series_id
        WHERE v.id = ?
          AND v.review_status = 'approved'
          AND v.is_active = 1
        """,
        (vehicle_id,),
    ).fetchone()
    if not row:
        return None

    cats = _get_vehicle_categories(conn, vehicle_id)
    gallery = get_vehicle_gallery(conn, vehicle_id)
    img_info = get_primary_vehicle_image(conn, vehicle_id)

    return {
        "id": row["id"],
        "brand": {
            "id": row["brand_id"],
            "name": row["brand_name"],
            "name_zh": row["brand_name_zh"],
            "country": row["brand_country"],
            "logo_url": resolve_preferred_image_url(conn, row["brand_logo_id"]),
        },
        "series": (
            {
                "id": row["series_id"],
                "name": row["series_name"],
                "name_zh": row["series_name_zh"],
            }
            if row["series_id"]
            else None
        ),
        "model_name": row["model_name"],
        "model_name_zh": row["model_name_zh"] or row["model_name"],
        "trim_name": row["trim_name"],
        "generation": row["generation"],
        "model_year": row["model_year"],
        "body_style": row["body_style"] or "轿车",
        "power_type": row["power_type"],
        "categories": cats,
        "category_names": [c["name"] for c in cats],
        "introduction_child": row["introduction_child"],
        "introduction_parent": row["introduction_parent"],
        "recognition_features": row["recognition_features"],
        "usage_description": row["usage_description"],
        **img_info,
        "images": gallery,
    }

