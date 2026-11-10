#!/usr/bin/env python3
"""本机待审核品牌、车系、车型与识别收件箱命令行审核工具。"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import db_session, initialize_database
from app.schemas import ReviewActionRequest, VehiclePatchRequest
from app.services.review_service import (
    approve_brand,
    approve_series,
    approve_vehicle,
    list_pending_brands,
    list_pending_series,
    list_pending_vehicles,
    list_recognition_inbox,
    patch_vehicle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="本机车型待审核队列管理工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="查看所有待审核品牌、车系、车型及识别待处理队列")

    approve_v = sub.add_parser("approve-vehicle", help="补全并审核通过指定车型")
    approve_v.add_argument("--id", type=int, required=True, help="待审核车型 ID")
    approve_v.add_argument("--intro", type=str, required=True, help="儿童版知识介绍")
    approve_v.add_argument("--category-id", type=int, default=1, help="主要分类 ID")

    args = parser.parse_args()
    initialize_database()

    with db_session() as conn:
        if args.cmd == "list":
            print("=== 待审核品牌 ===")
            for b in list_pending_brands(conn):
                print(f"  [Brand #{b['id']}] {b['name_zh']} ({b['name']})")

            print("\n=== 待审核车系 ===")
            for s in list_pending_series(conn):
                print(f"  [Series #{s['id']}] {s.get('brand_name_zh')} - {s['name_zh']}")

            print("\n=== 待审核具体车型 ===")
            for v in list_pending_vehicles(conn):
                print(
                    f"  [Vehicle #{v['id']}] {v.get('brand_name_zh') or v.get('brand_name_raw')} "
                    f"/ {v.get('series_name_zh') or v.get('series_name_raw')} / {v['model_name']}"
                )

            print("\n=== 识别待处理收件箱 (recognition_inbox) ===")
            for item in list_recognition_inbox(conn):
                print(f"  [Inbox #{item['id']}] 原因: {item['reason']}")

        elif args.cmd == "approve-vehicle":
            v_row = conn.execute(
                "SELECT * FROM vehicles WHERE id = ?", (args.id,)
            ).fetchone()
            if not v_row:
                print(f"未找到车型 ID={args.id}")
                return
            if v_row["brand_id"]:
                approve_brand(conn, int(v_row["brand_id"]), ReviewActionRequest())
            if v_row["series_id"]:
                approve_series(conn, int(v_row["series_id"]), ReviewActionRequest())
            patch_vehicle(
                conn,
                args.id,
                VehiclePatchRequest(
                    primary_category_id=args.category_id,
                    category_ids=[args.category_id],
                    introduction_child=args.intro,
                ),
            )
            approved = approve_vehicle(conn, args.id, ReviewActionRequest())
            print(f"车型 #{approved['id']} ({approved['model_name']}) 已审核通过并发布至儿童图鉴！")


if __name__ == "__main__":
    main()

