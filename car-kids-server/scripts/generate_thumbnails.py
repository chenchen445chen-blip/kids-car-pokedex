#!/usr/bin/env python3
"""离线批量生成图鉴缩略图脚本。"""

from pathlib import Path
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.db import db_session, initialize_database


def generate_all_thumbnails(max_size: tuple[int, int] = (480, 360)) -> None:
    initialize_database()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, relative_path FROM vehicle_images WHERE review_status = 'approved'"
        ).fetchall()
        for r in rows:
            src_path = settings.STORAGE_ROOT / r["relative_path"]
            if not src_path.exists():
                continue
            thumb_rel = f"catalog/thumbnails/thumb_{r['id']}.jpg"
            thumb_path = settings.STORAGE_ROOT / thumb_rel
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src_path) as img:
                rgb = img.convert("RGB")
                rgb.thumbnail(max_size)
                rgb.save(thumb_path, format="JPEG", quality=85)
            conn.execute(
                "UPDATE vehicle_images SET thumbnail_path = ? WHERE id = ?",
                (thumb_rel, r["id"]),
            )
    print("所有已审核图片的缩略图生成完毕。")


if __name__ == "__main__":
    generate_all_thumbnails()

