#!/usr/bin/env python3
"""
将本地离线整理的品牌/产品线/车系目录树及车辆图片批量同步至 SQLite 图鉴数据库。
"""

import argparse
import hashlib
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.db import db_session, initialize_database, normalize_text, utc_now_iso
from app.db.seed import _insert_image


BRAND_META = {
    "比亚迪": ("BYD", "china_independent", "中国", "科技 · 绿色 · 明天", (220, 38, 38)),
    "吉利": ("Geely", "china_independent", "中国", "快乐人生 · 吉利相伴", (37, 99, 235)),
    "奇瑞": ("Chery", "china_independent", "中国", "技术奇瑞 · 家庭伙伴", (100, 116, 139)),
    "长安": ("Changan", "china_independent", "中国", "智慧伙伴 · 安全出行", (30, 64, 175)),
    "哈弗": ("Haval", "china_independent", "中国", "专注 SUV · 翻山越岭", (75, 85, 99)),
    "五菱": ("Wuling", "china_independent", "中国", "灵巧实用 · 城市精灵", (220, 38, 38)),
    "大众": ("Volkswagen", "joint_venture", "德国", "经典可靠 · 家用常客", (30, 58, 138)),
    "丰田": ("Toyota", "joint_venture", "日本", "平顺耐用 · 省心出行", (225, 29, 72)),
    "本田": ("Honda", "joint_venture", "日本", "灵巧空间 · 活力出行", (71, 85, 105)),
    "日产": ("Nissan", "joint_venture", "日本", "舒适沙发 · 温馨家用", (185, 28, 28)),
    "奔驰": ("Mercedes-Benz", "luxury_import", "德国", "豪华 · 品质 · 未来", (51, 65, 85)),
    "宝马": ("BMW", "luxury_import", "德国", "蓝天白云 · 驾驶乐趣", (2, 132, 199)),
    "奥迪": ("Audi", "luxury_import", "德国", "四个圆环 · 科技大灯", (15, 23, 42)),
    "特斯拉": ("Tesla", "luxury_import", "美国", "纯电智能 · 简约未来", (239, 68, 68)),
    "别克": ("Buick", "joint_venture", "美国", "宽敞安静 · 舒适出行", (30, 64, 175)),
    "工程车辆": ("XCMG", "construction_machinery", "中国", "大力士工程机械", (245, 158, 11)),
    "特种与公共车辆": ("Special", "construction_machinery", "中国", "城市守护者", (220, 38, 38)),
}


def _ensure_brand(conn: sqlite3.Connection, brand_zh: str) -> int:
    actual_zh = brand_zh
    row = conn.execute(
        "SELECT id FROM brands WHERE name_zh = ? LIMIT 1", (actual_zh,)
    ).fetchone()
    if row:
        return int(row["id"])

    en_name, grp, country, slogan, color = BRAND_META.get(
        brand_zh, (brand_zh, "china_independent", "中国", "常见汽车品牌", (59, 130, 246))
    )
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO brands (
            name, name_zh, brand_group, country, slogan_child, introduction_child,
            review_status, is_active, sort_order, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'approved', 1, 100, ?, ?)
        """,
        (
            en_name,
            actual_zh,
            grp,
            country,
            slogan,
            f"{actual_zh}是道路上常见的汽车品牌。",
            now,
            now,
        ),
    )
    b_id = int(cur.lastrowid)
    logo_id = _insert_image(
        conn,
        rel_path=f"catalog/logos/brand_{b_id}.png",
        image_type="logo",
        bg_color=(248, 250, 252),
        accent_color=color,
        width=256,
        height=256,
        brand_id=b_id,
    )
    conn.execute("UPDATE brands SET logo_image_id = ? WHERE id = ?", (logo_id, b_id))
    conn.execute(
        """
        INSERT INTO brand_aliases (brand_id, alias, normalized_alias, language, source, review_status)
        VALUES (?, ?, ?, 'zh-CN', 'sync', 'approved')
        """,
        (b_id, actual_zh, normalize_text(actual_zh)),
    )
    return b_id


def _ensure_product_line(
    conn: sqlite3.Connection, brand_id: int, line_name: str
) -> int:
    row = conn.execute(
        """
        SELECT id FROM vehicle_series
        WHERE brand_id = ? AND name_zh = ? AND series_type = 'product_line'
        LIMIT 1
        """,
        (brand_id, line_name),
    ).fetchone()
    if row:
        return int(row["id"])

    now = utc_now_iso()
    code = f"pl_{brand_id}_{normalize_text(line_name)}"
    cur = conn.execute(
        """
        INSERT INTO vehicle_series (
            brand_id, parent_series_id, code, name, name_zh, series_type,
            body_type_label, introduction_child, review_status, is_active, sort_order,
            source_type, created_at, updated_at
        ) VALUES (?, NULL, ?, ?, ?, 'product_line', '产品线系列', ?, 'approved', 1, 10, 'import', ?, ?)
        """,
        (brand_id, code, line_name, line_name, f"{line_name}车型家族。", now, now),
    )
    return int(cur.lastrowid)


def _ensure_series_and_vehicle(
    conn: sqlite3.Connection,
    brand_id: int,
    brand_zh: str,
    series_zh: str,
    parent_line_id: Optional[int],
) -> tuple[int, int]:
    now = utc_now_iso()
    s_row = conn.execute(
        """
        SELECT id FROM vehicle_series
        WHERE brand_id = ? AND name_zh = ? AND series_type = 'vehicle_series'
        LIMIT 1
        """,
        (brand_id, series_zh),
    ).fetchone()

    if s_row:
        series_id = int(s_row["id"])
        if parent_line_id:
            conn.execute(
                "UPDATE vehicle_series SET parent_series_id = ? WHERE id = ?",
                (parent_line_id, series_id),
            )
    else:
        code = f"s_{brand_id}_{normalize_text(series_zh)}"
        body_label = (
            "SUV"
            if any(k in series_zh.upper() for k in ["SUV", "GL", "X", "Q", "CS", "瑞虎", "途", "宋", "唐", "元", "H6", "H9"])
            else "常见车系"
        )
        cur = conn.execute(
            """
            INSERT INTO vehicle_series (
                brand_id, parent_series_id, code, name, name_zh, series_type,
                body_type_label, introduction_child, review_status, is_active, sort_order,
                source_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'vehicle_series', ?, ?, 'approved', 1, 50, 'import', ?, ?)
            """,
            (
                brand_id,
                parent_line_id,
                code,
                series_zh,
                series_zh,
                body_label,
                f"{brand_zh}{series_zh}是道路上常见的代表车系，造型很有辨识度。",
                now,
                now,
            ),
        )
        series_id = int(cur.lastrowid)
        img_id = _insert_image(
            conn,
            rel_path=f"catalog/originals/series_{series_id}_main.png",
            image_type="real_photo",
            bg_color=(226, 232, 240),
            accent_color=(59, 130, 246),
            series_id=series_id,
            is_primary=1,
            sort_order=1,
        )
        conn.execute(
            "UPDATE vehicle_series SET cover_image_id = ? WHERE id = ?",
            (img_id, series_id),
        )
        conn.execute(
            """
            INSERT INTO vehicle_series_aliases (series_id, alias, normalized_alias, language, source, review_status)
            VALUES (?, ?, ?, 'zh-CN', 'sync', 'approved')
            """,
            (series_id, f"{brand_zh}{series_zh}", normalize_text(f"{brand_zh}{series_zh}")),
        )

    v_row = conn.execute(
        "SELECT id FROM vehicles WHERE series_id = ? LIMIT 1", (series_id,)
    ).fetchone()
    if v_row:
        vehicle_id = int(v_row["id"])
    else:
        cat_code = "family_car"
        if brand_zh == "工程车辆":
            cat_code = "construction"
        elif brand_zh == "特种与公共车辆":
            if series_zh in ("公交车", "校车"):
                cat_code = "public_transit"
            elif series_zh in ("厢式货车", "洒水车", "环卫垃圾车"):
                cat_code = "freight"
            else:
                cat_code = "special_purpose"
        elif series_zh in ("G级", "猛龙", "大狗", "H9", "普拉多", "Model X"):
            cat_code = "off_road"
        elif series_zh in ("宏光", "荣光", "征程"):
            cat_code = "freight"
        cat_row = conn.execute(
            "SELECT id FROM vehicle_categories WHERE code = ? LIMIT 1", (cat_code,)
        ).fetchone()
        prim_cat_id = int(cat_row["id"]) if cat_row else 1

        full_name = series_zh if brand_zh in ("工程车辆", "特种与公共车辆") else f"{brand_zh} {series_zh}"
        dedupe = normalize_text(f"{brand_zh}_{series_zh}_2024")
        cur_v = conn.execute(
            """
            INSERT INTO vehicles (
                brand_id, series_id, primary_category_id, model_name, model_name_zh,
                trim_name, model_year, body_style, power_type, introduction_child,
                recognition_features, usage_description, source_type, dedupe_key,
                review_status, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '标准版', 2024, '汽车', '常见动力', ?, ?, '日常出行与工作', 'import', ?, 'approved', 1, ?, ?)
            """,
            (
                brand_id,
                series_id,
                prim_cat_id,
                full_name,
                full_name,
                f"这是一辆{full_name}，我们在马路上经常可以看到它。",
                f"车头带有{brand_zh}标志与{series_zh}家族特征外观。",
                dedupe,
                now,
                now,
            ),
        )
        vehicle_id = int(cur_v.lastrowid)
        conn.execute(
            """
            INSERT OR IGNORE INTO vehicle_category_relations (vehicle_id, category_id, is_primary, created_at)
            VALUES (?, ?, 1, ?)
            """,
            (vehicle_id, prim_cat_id, now),
        )

    return series_id, vehicle_id


def _import_brand_logo(
    conn: sqlite3.Connection, logo_root: Path, brand_id: int, brand_zh: str
) -> int:
    """将 品牌车标/<品牌名>/ 下采集的真实车标图片同步至 vehicle_images 并更新 brands.logo_image_id。"""
    from core_img_helper import get_img_dimensions

    brand_logo_dir = logo_root / brand_zh
    if not brand_logo_dir.exists() or not brand_logo_dir.is_dir():
        return 0

    source_meta_map = _load_sources_csv_map(brand_logo_dir)
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    for img_file in sorted(brand_logo_dir.iterdir()):
        if not img_file.is_file() or img_file.suffix.lower() not in allowed_exts:
            continue
        raw = img_file.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        meta = source_meta_map.get(img_file.name) or source_meta_map.get(sha256) or {}
        orig_url = (meta.get("original_image_url") or "").strip() or None
        src_site = (meta.get("source_site") or "local_dataset").strip()
        page_url = (meta.get("page_url") or "").strip() or None
        lic_status = (meta.get("license_status") or "pending_authorization").strip()

        ext = img_file.suffix.lower()
        rel_path = f"catalog/logos/crawled_brand_{brand_id}_{sha256[:10]}{ext}"
        dest = settings.STORAGE_ROOT / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(img_file, dest)

        exists = conn.execute(
            "SELECT id FROM vehicle_images WHERE brand_id = ? AND image_type = 'logo' AND sha256 = ? LIMIT 1",
            (brand_id, sha256),
        ).fetchone()
        if exists:
            logo_img_id = int(exists["id"])
            conn.execute(
                """
                UPDATE vehicle_images
                SET source_url = COALESCE(?, source_url),
                    source_name = ?,
                    attribution = ?,
                    relative_path = ?
                WHERE id = ?
                """,
                (orig_url, src_site, page_url, rel_path, logo_img_id),
            )
            conn.execute("UPDATE brands SET logo_image_id = ? WHERE id = ?", (logo_img_id, brand_id))
            conn.execute(
                "DELETE FROM vehicle_images WHERE brand_id = ? AND image_type = 'logo' AND id != ?",
                (brand_id, logo_img_id),
            )
            return 0

        w, h = get_img_dimensions(raw)
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
        cur = conn.execute(
            """
            INSERT INTO vehicle_images (
                brand_id, image_type, relative_path, thumbnail_path,
                mime_type, width, height, file_size, sha256,
                source_name, source_url, license_info, attribution,
                review_status, is_primary, sort_order, created_at
            ) VALUES (?, 'logo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1, 0, ?)
            """,
            (
                brand_id,
                rel_path,
                rel_path,
                mime,
                w,
                h,
                len(raw),
                sha256,
                src_site,
                orig_url,
                lic_status,
                page_url,
                utc_now_iso(),
            ),
        )
        logo_img_id = int(cur.lastrowid)
        conn.execute("UPDATE brands SET logo_image_id = ? WHERE id = ?", (logo_img_id, brand_id))
        conn.execute(
            "DELETE FROM vehicle_images WHERE brand_id = ? AND image_type = 'logo' AND id != ?",
            (brand_id, logo_img_id),
        )
        return 1
    return 0


def sync_crawler_directory(crawler_root: Path, logo_root: Optional[Path] = None) -> tuple[int, int]:
    """扫描爬虫目录树，将所有品牌/产品线/车系、品牌车标及已下载的真实照片一一对应同步进 SQLite。"""
    initialize_database()
    if not crawler_root.exists():
        raise FileNotFoundError(f"爬虫图片目录不存在: {crawler_root}")
    if logo_root is None:
        logo_root = crawler_root.parent / "品牌车标"

    synced_series = 0
    imported_photos = 0
    valid_brand_ids: list[int] = []
    valid_series_ids: list[int] = []
    valid_vehicle_ids: list[int] = []

    with db_session() as conn:
        for brand_dir in sorted(crawler_root.iterdir()):
            if not brand_dir.is_dir() or brand_dir.name.startswith("."):
                continue
            brand_zh = brand_dir.name
            brand_id = _ensure_brand(conn, brand_zh)
            valid_brand_ids.append(brand_id)
            imported_photos += _import_brand_logo(conn, logo_root, brand_id, brand_zh)

            for sub_dir in sorted(brand_dir.iterdir()):
                if not sub_dir.is_dir() or sub_dir.name.startswith("."):
                    continue
                child_subdirs = [
                    p
                    for p in sub_dir.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                ]
                if child_subdirs:
                    line_id = _ensure_product_line(conn, brand_id, sub_dir.name)
                    valid_series_ids.append(line_id)
                    for leaf_dir in sorted(child_subdirs):
                        s_id, v_id = _ensure_series_and_vehicle(
                            conn, brand_id, brand_zh, leaf_dir.name, line_id
                        )
                        valid_series_ids.append(s_id)
                        valid_vehicle_ids.append(v_id)
                        synced_series += 1
                        imported_photos += _import_leaf_photos(
                            conn, leaf_dir, s_id, v_id
                        )
                else:
                    s_id, v_id = _ensure_series_and_vehicle(
                        conn, brand_id, brand_zh, sub_dir.name, None
                    )
                    valid_series_ids.append(s_id)
                    valid_vehicle_ids.append(v_id)
                    synced_series += 1
                    imported_photos += _import_leaf_photos(
                        conn, sub_dir, s_id, v_id
                    )

        # 清理不在 汽车图片/ 目录树中的多余种子品牌/车系/车型，以及所有非真实采集占位图片，确保 1:1 严格对应
        if valid_brand_ids:
            b_marks = ",".join("?" for _ in valid_brand_ids)
            conn.execute(f"DELETE FROM brands WHERE id NOT IN ({b_marks})", valid_brand_ids)
        if valid_series_ids:
            s_marks = ",".join("?" for _ in valid_series_ids)
            conn.execute(f"DELETE FROM vehicle_series WHERE id NOT IN ({s_marks})", valid_series_ids)
        if valid_vehicle_ids:
            v_marks = ",".join("?" for _ in valid_vehicle_ids)
            conn.execute(f"DELETE FROM vehicles WHERE id NOT IN ({v_marks})", valid_vehicle_ids)
            conn.execute(
                f"DELETE FROM vehicle_category_relations WHERE vehicle_id NOT IN ({v_marks})",
                valid_vehicle_ids,
            )
        conn.execute(
            """
            DELETE FROM vehicle_images
            WHERE image_type != 'logo'
              AND relative_path NOT LIKE 'catalog/originals/crawled_%'
            """
        )

    return synced_series, imported_photos


def _load_sources_csv_map(leaf_dir: Path) -> dict[str, dict]:
    """读取车系目录下的 sources.csv，按 local_filename 和 sha256 建立原始来源 URL 映射。"""
    import csv

    csv_path = leaf_dir / "sources.csv"
    mapping: dict[str, dict] = {}
    if not csv_path.exists():
        return mapping
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = (row.get("local_filename") or "").strip()
            sha = (row.get("sha256") or "").strip()
            if fname:
                mapping[fname] = row
            if sha:
                mapping[sha] = row
    return mapping


def _import_leaf_photos(
    conn: sqlite3.Connection, leaf_dir: Path, series_id: int, vehicle_id: int
) -> int:
    from core_img_helper import get_img_dimensions

    source_meta_map = _load_sources_csv_map(leaf_dir)
    count = 0
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    valid_sha_list: list[str] = []
    primary_img_id: Optional[int] = None

    for idx, img_file in enumerate(sorted(leaf_dir.iterdir())):
        if not img_file.is_file() or img_file.suffix.lower() not in allowed_exts:
            continue
        raw = img_file.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        valid_sha_list.append(sha256)
        meta = source_meta_map.get(img_file.name) or source_meta_map.get(sha256) or {}
        orig_url = (meta.get("original_image_url") or "").strip() or None
        src_site = (meta.get("source_site") or "local_dataset").strip()
        page_url = (meta.get("page_url") or "").strip() or None
        lic_status = (meta.get("license_status") or "pending_authorization").strip()

        ext = img_file.suffix.lower()
        rel_path = f"catalog/originals/crawled_s{series_id}_{sha256[:10]}{ext}"
        dest = settings.STORAGE_ROOT / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(img_file, dest)

        is_prim = 1 if idx == 0 else 0
        exists = conn.execute(
            "SELECT id, source_url FROM vehicle_images WHERE series_id = ? AND vehicle_id = ? AND sha256 = ? LIMIT 1",
            (series_id, vehicle_id, sha256),
        ).fetchone()
        if exists:
            img_id = int(exists["id"])
            conn.execute(
                """
                UPDATE vehicle_images
                SET source_url = COALESCE(?, source_url),
                    source_name = ?,
                    attribution = ?,
                    license_info = ?,
                    vehicle_id = ?,
                    series_id = ?,
                    relative_path = ?,
                    is_primary = ?,
                    sort_order = ?
                WHERE id = ?
                """,
                (
                    orig_url,
                    src_site,
                    page_url,
                    lic_status,
                    vehicle_id,
                    series_id,
                    rel_path,
                    is_prim,
                    idx,
                    img_id,
                ),
            )
            if primary_img_id is None:
                primary_img_id = img_id
            continue

        w, h = get_img_dimensions(raw)
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
        cur = conn.execute(
            """
            INSERT INTO vehicle_images (
                vehicle_id, series_id, image_type, relative_path, thumbnail_path,
                mime_type, width, height, file_size, sha256,
                source_name, source_url, license_info, attribution,
                review_status, is_primary, sort_order, created_at
            ) VALUES (?, ?, 'real_photo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)
            """,
            (
                vehicle_id,
                series_id,
                rel_path,
                rel_path,
                mime,
                w,
                h,
                len(raw),
                sha256,
                src_site,
                orig_url,
                lic_status,
                page_url,
                is_prim,
                idx,
                utc_now_iso(),
            ),
        )
        img_id = int(cur.lastrowid)
        if primary_img_id is None:
            primary_img_id = img_id
        count += 1

    # 清理该车系下已被替换掉的旧图片（如之前含广告或非官方库的旧图）
    if valid_sha_list:
        sha_marks = ",".join("?" for _ in valid_sha_list)
        conn.execute(
            f"""
            DELETE FROM vehicle_images
            WHERE series_id = ? AND image_type = 'real_photo'
              AND sha256 NOT IN ({sha_marks})
            """,
            [series_id, *valid_sha_list],
        )
    if primary_img_id is not None:
        conn.execute(
            "UPDATE vehicle_series SET cover_image_id = ? WHERE id = ?",
            (primary_img_id, series_id),
        )
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将本地汽车图片目录树同步到后端 SQLite")
    parser.add_argument(
        "--crawler-root",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "storage" / "import_source"),
        help="本地汽车图片数据集根目录路径",
    )
    args = parser.parse_args()
    s_cnt, p_cnt = sync_crawler_directory(Path(args.crawler_root))
    print(f"同步完成：共入库 {s_cnt} 个车系/车型，新导入 {p_cnt} 张图片！")
