import sqlite3
from typing import Optional

from app.services.image_service import (
    build_image_url,
    get_primary_vehicle_image,
    get_series_gallery,
    resolve_preferred_image_url,
)


def get_series_detail(conn: sqlite3.Connection, series_id: int) -> Optional[dict]:
    row = conn.execute(
        """
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
            b.name AS brand_name,
            b.name_zh AS brand_name_zh,
            b.logo_image_id AS brand_logo_id,
            ps.name_zh AS parent_series_name_zh
        FROM vehicle_series s
        JOIN brands b ON b.id = s.brand_id
        LEFT JOIN vehicle_series ps ON ps.id = s.parent_series_id
        WHERE s.id = ?
          AND s.review_status = 'approved'
          AND s.is_active = 1
          AND b.review_status = 'approved'
          AND b.is_active = 1
        """,
        (series_id,),
    ).fetchone()
    if not row:
        return None

    gallery = get_series_gallery(conn, series_id)

    v_rows = conn.execute(
        """
        SELECT
            v.id,
            v.model_name,
            v.model_name_zh,
            v.trim_name,
            v.model_year,
            v.body_style,
            v.power_type,
            v.introduction_child
        FROM vehicles v
        WHERE v.series_id = ?
          AND v.review_status = 'approved'
          AND v.is_active = 1
        ORDER BY v.model_year DESC, v.id ASC
        """,
        (series_id,),
    ).fetchall()

    vehicles = []
    for vr in v_rows:
        img_info = get_primary_vehicle_image(conn, vr["id"])
        vehicles.append(
            {
                "id": vr["id"],
                "model_name": vr["model_name"],
                "model_name_zh": vr["model_name_zh"] or row["name_zh"],
                "trim_name": vr["trim_name"],
                "model_year": vr["model_year"],
                "body_style": vr["body_style"] or row["body_type_label"],
                "power_type": vr["power_type"],
                "introduction_child": vr["introduction_child"],
                **img_info,
            }
        )

    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "name_zh": row["name_zh"],
        "full_title": f"{row['brand_name_zh']} {row['name_zh']}",
        "series_type": row["series_type"],
        "body_type_label": row["body_type_label"] or "豪华中大型轿车",
        "introduction_child": row["introduction_child"],
        "cover_image_url": (
            gallery[0]["url"]
            if gallery
            else resolve_preferred_image_url(conn, row["cover_image_id"])
        ),
        "gallery": gallery,
        "brand": {
            "id": row["brand_id"],
            "name": row["brand_name"],
            "name_zh": row["brand_name_zh"],
            "logo_url": build_image_url(row["brand_logo_id"]),
        },
        "parent_product_line": (
            {"id": row["parent_series_id"], "name_zh": row["parent_series_name_zh"]}
            if row["parent_series_id"]
            else None
        ),
        "vehicle_count": len(vehicles),
        "vehicles": vehicles,
    }

