from pathlib import Path
import sqlite3
from typing import Optional

from app.core.config import settings


IMAGE_PRIORITY_CASE = """
CASE
    WHEN source_url IS NOT NULL AND source_url != '' AND image_type = 'real_photo' THEN 0
    WHEN image_type = 'real_photo' THEN 1
    WHEN image_type = 'synthetic_model' THEN 2
    WHEN image_type = 'illustration' THEN 3
    WHEN image_type = 'logo' THEN 4
    ELSE 5
END
"""


def build_image_url(
    image_id: Optional[int], source_url: Optional[str] = None
) -> Optional[str]:
    """优先使用已去水印的本地受控图片接口 URL (/api/v1/images/{id})，若无则回退到 source_url。"""
    if image_id:
        return f"/api/v1/images/{image_id}"
    if source_url and source_url.strip().startswith(("http://", "https://")):
        return source_url.strip()
    return None


def resolve_preferred_image_url(
    conn: sqlite3.Connection, image_id: Optional[int]
) -> Optional[str]:
    """根据图片 ID 查询数据库，优先返回其原始来源 URL (source_url)，否则返回本地接口路径。"""
    if not image_id:
        return None
    row = conn.execute(
        "SELECT id, source_url FROM vehicle_images WHERE id = ? AND review_status = 'approved'",
        (image_id,),
    ).fetchone()
    if not row:
        return f"/api/v1/images/{image_id}"
    return build_image_url(row["id"], row["source_url"])


def get_primary_vehicle_image(conn: sqlite3.Connection, vehicle_id: int) -> dict:
    """按『带原始来源 URL 的真实照片 > 本地真实照片 > 仿真模型』优先级获取车型主图。"""
    row = conn.execute(
        f"""
        SELECT id, image_type, width, height, source_url, source_name
        FROM vehicle_images
        WHERE vehicle_id = ? AND review_status = 'approved'
        ORDER BY {IMAGE_PRIORITY_CASE} ASC, is_primary DESC, sort_order ASC, id DESC
        LIMIT 1
        """,
        (vehicle_id,),
    ).fetchone()
    if row:
        preferred_url = build_image_url(row["id"], row["source_url"])
        return {
            "cover_image_id": row["id"],
            "cover_image_url": preferred_url,
            "source_url": row["source_url"],
            "local_image_url": f"/api/v1/images/{row['id']}",
            "source_name": row["source_name"],
            "cover_image_type": row["image_type"],
            "is_model_image": row["image_type"] == "synthetic_model",
        }
    return {
        "cover_image_id": None,
        "cover_image_url": None,
        "source_url": None,
        "local_image_url": None,
        "source_name": None,
        "cover_image_type": "placeholder",
        "is_model_image": False,
    }


def get_vehicle_gallery(conn: sqlite3.Connection, vehicle_id: int) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT id, image_type, width, height, is_primary, sort_order, source_url, source_name, attribution
        FROM vehicle_images
        WHERE vehicle_id = ? AND review_status = 'approved'
        ORDER BY {IMAGE_PRIORITY_CASE} ASC, is_primary DESC, sort_order ASC, id DESC
        """,
        (vehicle_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "url": build_image_url(r["id"], r["source_url"]),
            "source_url": r["source_url"],
            "local_image_url": f"/api/v1/images/{r['id']}",
            "source_name": r["source_name"],
            "image_type": r["image_type"],
            "image_type_label": (
                "仿真模型"
                if r["image_type"] == "synthetic_model"
                else ("示意图" if r["image_type"] == "illustration" else "真实实拍")
            ),
            "width": r["width"],
            "height": r["height"],
            "is_primary": bool(r["is_primary"]),
            "sort_order": r["sort_order"],
            "attribution": r["attribution"],
        }
        for r in rows
    ]


def get_series_gallery(conn: sqlite3.Connection, series_id: int) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT id, image_type, width, height, is_primary, sort_order, source_url, source_name
        FROM vehicle_images
        WHERE series_id = ? AND review_status = 'approved'
        ORDER BY {IMAGE_PRIORITY_CASE} ASC, is_primary DESC, sort_order ASC, id DESC
        """,
        (series_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "url": build_image_url(r["id"], r["source_url"]),
            "source_url": r["source_url"],
            "local_image_url": f"/api/v1/images/{r['id']}",
            "source_name": r["source_name"],
            "image_type": r["image_type"],
            "width": r["width"],
            "height": r["height"],
            "is_primary": bool(r["is_primary"]),
        }
        for r in rows
    ]


def resolve_approved_image_file(
    conn: sqlite3.Connection, image_id: int
) -> Optional[tuple[Path, str]]:
    """安全解析受控本地图片路径，防止 ../ 目录穿越并校验审核状态。"""
    row = conn.execute(
        """
        SELECT relative_path, mime_type
        FROM vehicle_images
        WHERE id = ? AND review_status = 'approved'
        """,
        (image_id,),
    ).fetchone()
    if not row:
        return None

    rel_path = row["relative_path"]
    if ".." in rel_path or rel_path.startswith("/"):
        return None

    storage_root = settings.STORAGE_ROOT.resolve()
    target_path = (storage_root / rel_path).resolve()

    if not str(target_path).startswith(str(storage_root)):
        return None
    if not target_path.exists() or not target_path.is_file():
        return None

    return target_path, row["mime_type"]
