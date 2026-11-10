#!/usr/bin/env python3
"""SQLite 数据库与 storage/catalog 图鉴图片备份脚本。"""

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def run_backup(backup_root: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = backup_root.resolve() / f"backup_{ts}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if settings.DATABASE_PATH.exists():
        db_backup_path = dest_dir / "car_kids.db"
        src_conn = sqlite3.connect(str(settings.DATABASE_PATH))
        dst_conn = sqlite3.connect(str(db_backup_path))
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()

    catalog_dir = settings.STORAGE_ROOT / "catalog"
    if catalog_dir.exists():
        shutil.copytree(catalog_dir, dest_dir / "catalog", dirs_exist_ok=True)

    return dest_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="备份 SQLite 数据库与正式图鉴图片目录")
    parser.add_argument(
        "--dest",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "backups"),
        help="备份输出目录",
    )
    args = parser.parse_args()
    out = run_backup(Path(args.dest))
    print(f"备份完成，已保存至: {out}")

