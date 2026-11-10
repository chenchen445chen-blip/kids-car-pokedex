import hashlib
from io import BytesIO
from pathlib import Path
import sqlite3
import struct
from typing import Optional
import zlib

from app.core.config import settings
from app.db.database import normalize_text, utc_now_iso


def _encode_solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """使用标准库生成纯色有效 PNG 二进制数据。"""
    raw_row = b"\x00" + bytes(rgb) * width
    raw_data = raw_row * height

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw_data, level=6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", idat)
        + make_chunk(b"IEND", b"")
    )


def _create_sample_image(
    rel_path: str,
    width: int,
    height: int,
    bg_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
) -> tuple[str, int]:
    """在本地 storage 目录生成合规的示例卡片或车标 PNG，并返回 (sha256, file_size)。"""
    full_path: Path = settings.STORAGE_ROOT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    if not full_path.exists():
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)
            pad = min(width, height) // 8
            draw.rounded_rectangle(
                [pad, pad, width - pad, height - pad],
                radius=24,
                fill=accent_color,
            )
            buf = BytesIO()
            img.save(buf, format="PNG")
            full_path.write_bytes(buf.getvalue())
        except ImportError:
            full_path.write_bytes(_encode_solid_png(width, height, accent_color))

    raw = full_path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _insert_image(
    conn: sqlite3.Connection,
    rel_path: str,
    image_type: str,
    bg_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    width: int = 800,
    height: int = 600,
    brand_id: Optional[int] = None,
    series_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    is_primary: int = 1,
    sort_order: int = 1,
) -> int:
    sha256, file_size = _create_sample_image(rel_path, width, height, bg_color, accent_color)
    cur = conn.execute(
        """
        INSERT INTO vehicle_images (
            vehicle_id, series_id, brand_id, image_type, relative_path, thumbnail_path,
            mime_type, width, height, file_size, sha256, source_name, license_info,
            review_status, is_primary, sort_order, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'image/png', ?, ?, ?, ?, '系统内置合规图库', '自有授权展示素材', 'approved', ?, ?, ?)
        """,
        (
            vehicle_id,
            series_id,
            brand_id,
            image_type,
            rel_path,
            rel_path,
            width,
            height,
            file_size,
            sha256,
            is_primary,
            sort_order,
            utc_now_iso(),
        ),
    )
    return int(cur.lastrowid)


def seed_initial_data(conn: sqlite3.Connection) -> None:
    """当数据库为空时，自动导入需求文档 P0 分类、品牌、产品线/车系和代表车型。"""
    row = conn.execute("SELECT COUNT(1) AS cnt FROM vehicle_categories").fetchone()
    if row and row["cnt"] > 0:
        return

    now = utc_now_iso()

    # 1. 一级车辆类型分类（对齐需求文档 3.2.1 A 与 UI 设计稿「按类型」列表）
    primary_categories = [
        ("family_car", "家用车", "日常家庭出行常见车辆", 10),
        ("off_road", "越野车", "强调复杂路况与户外越野能力", 20),
        ("construction", "工程车", "施工、道路和建筑作业工程车辆", 30),
        ("freight", "货运车辆", "运输货物的卡车与厢式货车", 40),
        ("public_transit", "公共交通", "公交车、校车等服务大家的车辆", 50),
        ("special_purpose", "特种车辆", "消防车、救护车、警车等执行专门任务的车辆", 60),
        ("motorcycle_other", "摩托及其他", "摩托车、房车等特色车辆", 70),
    ]
    cat_map: dict[str, int] = {}
    for code, name, desc, order in primary_categories:
        cur = conn.execute(
            """
            INSERT INTO vehicle_categories (code, name, parent_id, description, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, 1, ?, ?)
            """,
            (code, name, desc, order, now, now),
        )
        cat_map[code] = int(cur.lastrowid)

    # 二级分类
    sub_categories = [
        ("sedan", "轿车", "family_car", 11),
        ("suv", "SUV", "family_car", 12),
        ("mpv", "MPV", "family_car", 13),
        ("excavator", "挖掘机", "construction", 31),
        ("loader", "装载机", "construction", 32),
        ("bulldozer", "推土机", "construction", 33),
        ("crane", "起重机", "construction", 34),
        ("road_roller", "压路机", "construction", 35),
        ("mixer_truck", "混凝土搅拌车", "construction", 36),
    ]
    for code, name, parent_code, order in sub_categories:
        cur = conn.execute(
            """
            INSERT INTO vehicle_categories (code, name, parent_id, description, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (code, name, cat_map[parent_code], name, order, now, now),
        )
        cat_map[code] = int(cur.lastrowid)

    # 2. 品牌及别名（对齐 UI 设计稿九宫格：比亚迪、吉利、大众、丰田、本田、奔驰、宝马、奥迪、特斯拉 + P0 热门品牌）
    brands_seed = [
        ("BYD", "比亚迪", "china_independent", "中国", "科技 · 绿色 · 明天", "比亚迪是中国常见的汽车品牌，有很多绿牌新能源车。", ["比亚迪", "BYD", "比亚迪汽车"], 10, (220, 38, 38)),
        ("Geely", "吉利", "china_independent", "中国", "快乐人生 · 吉利相伴", "吉利汽车是路上经常能看到的中国汽车品牌。", ["吉利", "Geely", "吉利汽车"], 20, (37, 99, 235)),
        ("Volkswagen", "大众", "joint_venture", "德国", "经典可靠 · 家用常客", "大众的车标由字母 V 和 W 组成，像两个叠在一起的字母。", ["大众", "VW", "Volkswagen", "一汽大众", "上汽大众"], 30, (30, 58, 138)),
        ("Toyota", "丰田", "joint_venture", "日本", "平顺耐用 · 省心出行", "丰田的车标由三个椭圆组成，在马路上非常常见。", ["丰田", "Toyota", "一汽丰田", "广汽丰田"], 40, (225, 29, 72)),
        ("Honda", "本田", "joint_venture", "日本", "灵巧空间 · 活力出行", "本田的车标是一个大大的字母 H。", ["本田", "Honda", "广汽本田", "东风本田"], 50, (71, 85, 105)),
        ("Mercedes-Benz", "奔驰", "luxury_import", "德国", "豪华 · 品质 · 未来", "奔驰的车标是一颗闪亮的三叉星，坐起来宽敞又舒服。", ["奔驰", "Mercedes-Benz", "Mercedes", "Benz", "梅赛德斯奔驰", "北京奔驰"], 60, (51, 65, 85)),
        ("BMW", "宝马", "luxury_import", "德国", "蓝天白云 · 驾驶乐趣", "宝马的车标是蓝白相间的圆环，车头有两个像鼻孔一样的格栅。", ["宝马", "BMW", "华晨宝马"], 70, (2, 132, 199)),
        ("Audi", "奥迪", "luxury_import", "德国", "四个圆环 · 科技大灯", "奥迪的车标由四个紧紧相连的圆环组成，非常好认。", ["奥迪", "Audi", "一汽奥迪"], 80, (15, 23, 42)),
        ("Tesla", "特斯拉", "luxury_import", "美国", "纯电智能 · 简约未来", "特斯拉是纯电动汽车，车头没有传统进气格栅，车标像字母 T。", ["特斯拉", "Tesla"], 90, (239, 68, 68)),
        ("Chery", "奇瑞", "china_independent", "中国", "技术奇瑞 · 家庭伙伴", "奇瑞是中国自主汽车品牌，有许多空间宽敞的 SUV。", ["奇瑞", "Chery"], 100, (100, 116, 139)),
        ("Changan", "长安", "china_independent", "中国", "智慧伙伴 · 安全出行", "长安汽车有着像字母 V 一样的对称车标。", ["长安", "Changan", "长安汽车"], 110, (30, 64, 175)),
        ("Haval", "哈弗", "china_independent", "中国", "专注 SUV · 翻山越岭", "哈弗的车标是英文字母 HAVAL，路上有很多哈弗 SUV。", ["哈弗", "Haval"], 120, (75, 85, 99)),
        ("Wuling", "五菱", "china_independent", "中国", "灵巧实用 · 城市精灵", "五菱的车标由五个鲜红的菱形组成，小巧又可爱。", ["五菱", "Wuling", "上汽通用五菱"], 130, (220, 38, 38)),
        ("Li Auto", "理想", "china_nev", "中国", "移动的家 · 家庭 SUV", "理想汽车空间很大，车头有一条长长的星环灯带。", ["理想", "Li Auto", "理想汽车"], 140, (16, 185, 129)),
        ("Xiaomi", "小米汽车", "china_nev", "中国", "科技轿跑 · 活力色彩", "小米汽车车身线条流畅，有很多鲜艳好看的颜色。", ["小米汽车", "小米", "Xiaomi"], 150, (249, 115, 22)),
        ("XCMG", "徐工", "construction_machinery", "中国", "大力士工程机械", "徐工制造各种黄色的工程车，比如大挖掘机和起重机。", ["徐工", "XCMG", "工程车品牌"], 160, (245, 158, 11)),
    ]

    brand_map: dict[str, int] = {}
    for name, name_zh, grp, country, slogan, intro, aliases, order, color in brands_seed:
        cur = conn.execute(
            """
            INSERT INTO brands (
                parent_brand_id, name, name_zh, brand_group, country,
                slogan_child, introduction_child, review_status, is_active, sort_order,
                created_at, updated_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, 'approved', 1, ?, ?, ?)
            """,
            (name, name_zh, grp, country, slogan, intro, order, now, now),
        )
        b_id = int(cur.lastrowid)
        brand_map[name_zh] = b_id

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

        for alias in aliases:
            conn.execute(
                """
                INSERT INTO brand_aliases (brand_id, alias, normalized_alias, language, source, review_status)
                VALUES (?, ?, ?, 'zh-CN', 'seed', 'approved')
                """,
                (b_id, alias, normalize_text(alias)),
            )

    # 3. 产品线与车系（重点还原奔驰 C级/E级/S级、宝马 3系、比亚迪王朝/海洋、丰田/大众/特斯拉等）
    def add_series(
        brand_zh: str,
        code: str,
        name: str,
        name_zh: str,
        body_label: str,
        intro: str,
        aliases: list[str],
        order: int,
        series_type: str = "vehicle_series",
        parent_series_id: Optional[int] = None,
        color: tuple[int, int, int] = (59, 130, 246),
    ) -> int:
        b_id = brand_map[brand_zh]
        cur = conn.execute(
            """
            INSERT INTO vehicle_series (
                brand_id, parent_series_id, code, name, name_zh, series_type,
                body_type_label, introduction_child, review_status, is_active, sort_order,
                source_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1, ?, 'manual', ?, ?)
            """,
            (b_id, parent_series_id, code, name, name_zh, series_type, body_label, intro, order, now, now),
        )
        s_id = int(cur.lastrowid)
        img_id = _insert_image(
            conn,
            rel_path=f"catalog/originals/series_{s_id}_main.png",
            image_type="real_photo",
            bg_color=(226, 232, 240),
            accent_color=color,
            series_id=s_id,
            is_primary=1,
            sort_order=1,
        )
        # 额外补充两张多角度实拍图（对齐设计稿「E级」详情页的 3 张角度缩略图）
        _insert_image(
            conn,
            rel_path=f"catalog/originals/series_{s_id}_interior.png",
            image_type="real_photo",
            bg_color=(203, 213, 225),
            accent_color=color,
            series_id=s_id,
            is_primary=0,
            sort_order=2,
        )
        _insert_image(
            conn,
            rel_path=f"catalog/originals/series_{s_id}_rear.png",
            image_type="real_photo",
            bg_color=(215, 222, 232),
            accent_color=color,
            series_id=s_id,
            is_primary=0,
            sort_order=3,
        )
        conn.execute("UPDATE vehicle_series SET cover_image_id = ? WHERE id = ?", (img_id, s_id))

        for al in aliases:
            conn.execute(
                """
                INSERT INTO vehicle_series_aliases (series_id, alias, normalized_alias, language, source, review_status)
                VALUES (?, ?, ?, 'zh-CN', 'seed', 'approved')
                """,
                (s_id, al, normalize_text(al)),
            )
        return s_id

    # 奔驰车系（对应设计稿下排第2、3张图：C级、E级、S级、GLC、G级）
    mb_c_id = add_series(
        "奔驰", "mb_c_class", "C-Class", "C级", "豪华中型轿车",
        "奔驰C级是一辆时尚灵巧的豪华轿车，适合日常城市出行。",
        ["C级", "奔驰C级", "C-Class", "奔驰C"], 10, color=(148, 163, 184)
    )
    mb_e_id = add_series(
        "奔驰", "mb_e_class", "E-Class", "E级", "豪华中大型轿车",
        "奔驰E级是一款豪华商务轿车，兼顾舒适与性能。",
        ["E级", "奔驰E级", "E-Class", "奔驰E"], 20, color=(100, 116, 139)
    )
    mb_s_id = add_series(
        "奔驰", "mb_s_class", "S-Class", "S级", "豪华大型轿车",
        "奔驰S级车身修长稳重，后排座椅非常宽敞舒适。",
        ["S级", "奔驰S级", "S-Class", "奔驰S"], 30, color=(51, 65, 85)
    )
    mb_glc_id = add_series(
        "奔驰", "mb_glc", "GLC", "GLC", "豪华中型SUV",
        "奔驰GLC是一辆底盘较高的家用SUV，能装下全家的行李。",
        ["GLC", "奔驰GLC", "GLC L"], 40, color=(71, 85, 105)
    )

    # 宝马车系（对应设计稿上排第3张识别结果图：宝马 3系）
    bmw_3_id = add_series(
        "宝马", "bmw_3_series", "3 Series", "3系", "家用车 · 轿车",
        "宝马3系是一款受欢迎的豪华轿车。",
        ["3系", "宝马3系", "3 Series", "BMW 3系"], 10, color=(220, 38, 38)
    )
    bmw_x5_id = add_series(
        "宝马", "bmw_x5", "X5", "X5", "中大型SUV",
        "宝马X5体型高大威猛，适合全家去远方旅行。",
        ["X5", "宝马X5", "BMW X5"], 20, color=(37, 99, 235)
    )

    # 比亚迪王朝/海洋产品线及车系
    byd_dynasty_id = add_series(
        "比亚迪", "byd_dynasty", "Dynasty", "王朝系列", "产品线分组",
        "比亚迪王朝系列以中国朝代命名，车标带有汉字。",
        ["王朝", "王朝网", "王朝系列"], 5, series_type="product_line", color=(185, 28, 28)
    )
    byd_ocean_id = add_series(
        "比亚迪", "byd_ocean", "Ocean", "海洋系列", "产品线分组",
        "比亚迪海洋系列以海洋生物和舰艇命名，造型活泼可爱。",
        ["海洋", "海洋网", "海洋系列"], 6, series_type="product_line", color=(14, 165, 233)
    )
    byd_qin_id = add_series(
        "比亚迪", "byd_qin", "Qin", "秦", "家用轿车",
        "比亚迪秦是一辆节能环保的家用轿车，车头写着汉字“秦”。",
        ["秦", "比亚迪秦", "秦PLUS"], 10, parent_series_id=byd_dynasty_id, color=(220, 38, 38)
    )
    byd_han_id = add_series(
        "比亚迪", "byd_han", "Han", "汉", "中大型轿车",
        "比亚迪汉造型大气流畅，车头有着漂亮的汉字“汉”车标。",
        ["汉", "比亚迪汉", "汉EV", "汉DM-i"], 20, parent_series_id=byd_dynasty_id, color=(153, 27, 27)
    )
    byd_seagull_id = add_series(
        "比亚迪", "byd_seagull", "Seagull", "海鸥", "小型纯电车",
        "比亚迪海鸥体型小巧灵活，像海边飞翔的小海鸥。",
        ["海鸥", "比亚迪海鸥"], 30, parent_series_id=byd_ocean_id, color=(56, 189, 248)
    )

    # 其他常见品牌代表车系
    geely_xyl_id = add_series(
        "吉利", "geely_xingyue_l", "Xingyue L", "星越L", "家用SUV",
        "吉利星越L是一辆空间宽敞的家用SUV，前脸有直瀑式格栅。",
        ["星越L", "吉利星越L"], 10, color=(37, 99, 235)
    )
    vw_lavida_id = add_series(
        "大众", "vw_lavida", "Lavida", "朗逸", "家用轿车",
        "大众朗逸是马路上非常常见的家用小轿车。",
        ["朗逸", "大众朗逸", "Lavida"], 10, color=(59, 130, 246)
    )
    toyota_corolla_id = add_series(
        "丰田", "toyota_corolla", "Corolla", "卡罗拉", "家用轿车",
        "丰田卡罗拉是一辆经济耐用的家用轿车，陪伴许多家庭出行。",
        ["卡罗拉", "丰田卡罗拉", "Corolla"], 10, color=(225, 29, 72)
    )
    honda_civic_id = add_series(
        "本田", "honda_civic", "Civic", "思域", "家用轿车",
        "本田思域造型运动时尚，在城市道路上十分常见。",
        ["思域", "本田思域", "Civic"], 10, color=(37, 99, 235)
    )
    audi_a6l_id = add_series(
        "奥迪", "audi_a6l", "A6L", "A6L", "豪华中大型轿车",
        "奥迪A6L车身沉稳大气，拥有酷炫的科技车灯。",
        ["A6L", "奥迪A6L", "奥迪A6"], 10, color=(30, 41, 59)
    )
    tesla_my_id = add_series(
        "特斯拉", "tesla_model_y", "Model Y", "Model Y", "纯电家用SUV",
        "特斯拉Model Y是一辆纯电动SUV，车顶有一整块大玻璃。",
        ["Model Y", "特斯拉Model Y", "ModelY"], 10, color=(239, 68, 68)
    )

    # 工程车系列（对应设计稿右上「工程车」分类页：挖掘机、装载机、推土机、起重机、压路机、混凝土搅拌车）
    construction_items = [
        ("excavator", "挖掘机", "Excavator", "工程作业车", "这是一辆挖掘机。它有一只长长的铁臂和大铲斗，可以帮助工人叔叔挖土和修路。", "长长的机械臂、铲斗和履带底盘"),
        ("loader", "装载机", "Wheel Loader", "工程作业车", "这是一辆装载机。它前面的大铲斗像双手一样，能把沙石装进卡车里。", "车头宽大的铲斗与高大的橡胶轮胎"),
        ("bulldozer", "推土机", "Bulldozer", "工程作业车", "这是一辆推土机。它车头装着宽宽的推土铲，能把凹凸不平的泥地推平整。", "车头巨大的金属推土刀与厚重履带"),
        ("crane", "起重机", "Truck Crane", "工程作业车", "这是一辆起重机。它的吊臂可以伸得像长颈鹿脖子一样高，能把重物稳稳吊起来。", "可伸缩的长长吊臂、吊钩和车身支腿"),
        ("road_roller", "压路机", "Road Roller", "工程作业车", "这是一辆压路机。它前面有一个沉甸甸的大铁轮，走过的地方马路就会变得平平整整。", "车头巨大的圆柱形钢轮"),
        ("mixer_truck", "混凝土搅拌车", "Concrete Mixer", "工程作业车", "这是一辆混凝土搅拌车。它背着一个不停旋转的大圆肚子，也叫田螺车。", "车背上倾斜旋转的椭圆形搅拌罐"),
    ]

    # 4. 具体车型数据（含设计稿中的「2024款 奔驰 E级」、「宝马 3系」及 6 种工程车）
    def add_vehicle(
        brand_zh: str,
        series_id: int,
        primary_cat_code: str,
        extra_cat_codes: list[str],
        model_name: str,
        model_name_zh: str,
        trim_name: str,
        model_year: int,
        body_style: str,
        power_type: str,
        intro_child: str,
        features: str,
        usage_desc: str,
        aliases: list[str],
        color: tuple[int, int, int] = (59, 130, 246),
        image_type: str = "real_photo",
    ) -> int:
        b_id = brand_map[brand_zh]
        prim_cat_id = cat_map[primary_cat_code]
        dedupe = normalize_text(f"{brand_zh}_{model_name}_{model_year}_{trim_name}")
        cur = conn.execute(
            """
            INSERT INTO vehicles (
                brand_id, series_id, primary_category_id, model_name, model_name_zh,
                trim_name, model_year, body_style, power_type, introduction_child,
                recognition_features, usage_description, source_type, dedupe_key,
                review_status, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, 'approved', 1, ?, ?)
            """,
            (
                b_id, series_id, prim_cat_id, model_name, model_name_zh,
                trim_name, model_year, body_style, power_type, intro_child,
                features, usage_desc, dedupe, now, now,
            ),
        )
        v_id = int(cur.lastrowid)

        all_cats = [primary_cat_code] + [c for c in extra_cat_codes if c != primary_cat_code]
        for idx, c_code in enumerate(all_cats):
            conn.execute(
                """
                INSERT INTO vehicle_category_relations (vehicle_id, category_id, is_primary, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (v_id, cat_map[c_code], 1 if idx == 0 else 0, now),
            )

        _insert_image(
            conn,
            rel_path=f"catalog/originals/vehicle_{v_id}_main.png",
            image_type=image_type,
            bg_color=(241, 245, 249),
            accent_color=color,
            vehicle_id=v_id,
            is_primary=1,
            sort_order=1,
        )

        for al in aliases:
            conn.execute(
                """
                INSERT INTO vehicle_aliases (vehicle_id, alias, normalized_alias, language, source, review_status)
                VALUES (?, ?, ?, 'zh-CN', 'seed', 'approved')
                """,
                (v_id, al, normalize_text(al)),
            )
        return v_id

    # 奔驰 E级 具体车型（对齐设计稿下排第4张图：2024款 奔驰 E级 · 轿车 / 奔驰 / 家用车 / 这是一款豪华轿车，适合家庭出行。）
    add_vehicle(
        brand_zh="奔驰",
        series_id=mb_e_id,
        primary_cat_code="family_car",
        extra_cat_codes=["sedan"],
        model_name="Mercedes-Benz E 300 L",
        model_name_zh="奔驰 E级",
        trim_name="E 300 L 时尚型",
        model_year=2024,
        body_style="轿车",
        power_type="燃油+48V轻混",
        intro_child="这是一款豪华轿车，适合家庭出行。",
        features="车头有三叉星徽车标，花生造型前大灯和星徽尾灯十分醒目。",
        usage_desc="家庭出行与商务乘坐",
        aliases=["奔驰E300L", "2024款奔驰E级", "E 300 L", "E300L"],
        color=(100, 116, 139),
    )

    add_vehicle(
        brand_zh="奔驰",
        series_id=mb_c_id,
        primary_cat_code="family_car",
        extra_cat_codes=["sedan"],
        model_name="Mercedes-Benz C 260 L",
        model_name_zh="奔驰 C级",
        trim_name="C 260 L 运动版",
        model_year=2024,
        body_style="轿车",
        power_type="燃油+48V轻混",
        intro_child="这是一辆动感漂亮的奔驰C级轿车，车头正中间有大大的三叉星车标。",
        features="星河格栅搭配大尺寸三叉星车标。",
        usage_desc="城市日常代步与家庭出行",
        aliases=["奔驰C260L", "C 260 L", "C260L"],
        color=(148, 163, 184),
    )

    add_vehicle(
        brand_zh="奔驰",
        series_id=mb_s_id,
        primary_cat_code="family_car",
        extra_cat_codes=["sedan"],
        model_name="Mercedes-Benz S 400 L",
        model_name_zh="奔驰 S级",
        trim_name="S 400 L 商务型",
        model_year=2024,
        body_style="轿车",
        power_type="燃油+48V轻混",
        intro_child="这是奔驰家族里最大的轿车S级，车头立着一颗精致的三叉星立标。",
        features="修长的车身、盾形镀铬前格栅与引擎盖立标。",
        usage_desc="长途舒适出行与礼宾接待",
        aliases=["奔驰S400L", "S 400 L", "S400L"],
        color=(51, 65, 85),
    )

    # 宝马 3系 具体车型（对齐设计稿上排第3张图：宝马 3系 · 家用车·轿车 · 宝马3系是一款受欢迎的豪华轿车。）
    add_vehicle(
        brand_zh="宝马",
        series_id=bmw_3_id,
        primary_cat_code="family_car",
        extra_cat_codes=["sedan"],
        model_name="BMW 325Li",
        model_name_zh="宝马 3系",
        trim_name="325Li M运动套装",
        model_year=2024,
        body_style="轿车",
        power_type="燃油",
        intro_child="宝马3系是一款受欢迎的豪华轿车。",
        features="蓝白圆环车标、双肾形进气格栅以及双L形天使眼大灯。",
        usage_desc="日常家庭出行",
        aliases=["宝马325Li", "325Li", "宝马3系"],
        color=(220, 38, 38),
    )

    add_vehicle(
        brand_zh="宝马",
        series_id=bmw_x5_id,
        primary_cat_code="family_car",
        extra_cat_codes=["suv", "off_road"],
        model_name="BMW X5 xDrive40Li",
        model_name_zh="宝马 X5",
        trim_name="xDrive40Li",
        model_year=2024,
        body_style="SUV",
        power_type="燃油",
        intro_child="这是一辆高大宽敞的宝马X5 SUV，既能城市代步也能去郊外游玩。",
        features="宽大的双肾格栅、高底盘 SUV 车身。",
        usage_desc="家庭出游与长途旅行",
        aliases=["宝马X5", "X5"],
        color=(37, 99, 235),
    )

    # 比亚迪秦 PLUS DM-i
    add_vehicle(
        brand_zh="比亚迪",
        series_id=byd_qin_id,
        primary_cat_code="family_car",
        extra_cat_codes=["sedan"],
        model_name="BYD Qin PLUS DM-i",
        model_name_zh="比亚迪 秦 PLUS DM-i",
        trim_name="荣耀版",
        model_year=2024,
        body_style="轿车",
        power_type="插电混动",
        intro_child="这是一辆挂着绿色车牌的比亚迪秦轿车，车标是汉字“秦”。",
        features="Dragon Face 龙颜前脸、中文“秦”字车标与贯穿式尾灯。",
        usage_desc="日常家庭代步出行",
        aliases=["秦PLUS", "秦PLUS DM-i", "比亚迪秦PLUS"],
        color=(220, 38, 38),
    )

    # 特斯拉 Model Y
    add_vehicle(
        brand_zh="特斯拉",
        series_id=tesla_my_id,
        primary_cat_code="family_car",
        extra_cat_codes=["suv"],
        model_name="Tesla Model Y",
        model_name_zh="特斯拉 Model Y",
        trim_name="后轮驱动版",
        model_year=2024,
        body_style="SUV",
        power_type="纯电动",
        intro_child="这是一辆不用加油只用充电的特斯拉Model Y，车门把手是隐藏式的。",
        features="封闭式前脸、T字形车标与溜背式全景玻璃车顶。",
        usage_desc="家庭日常环保出行",
        aliases=["Model Y", "特斯拉Model Y"],
        color=(239, 68, 68),
    )

    # 6 款工程车（对齐设计稿右上第5张图「工程车」：挖掘机、装载机、推土机、起重机、压路机、混凝土搅拌车）
    for idx, (sub_code, zh_name, en_name, label, intro, feat) in enumerate(construction_items, start=1):
        s_id = add_series(
            "徐工",
            f"xcmg_{sub_code}",
            en_name,
            zh_name,
            label,
            intro,
            [zh_name, en_name],
            idx * 10,
            color=(245, 158, 11),
        )
        add_vehicle(
            brand_zh="徐工",
            series_id=s_id,
            primary_cat_code="construction",
            extra_cat_codes=[sub_code],
            model_name=en_name,
            model_name_zh=zh_name,
            trim_name="标准工程型",
            model_year=2024,
            body_style="工程车",
            power_type="柴油动力",
            intro_child=intro,
            features=feat,
            usage_desc="建筑工地与道路施工作业",
            aliases=[zh_name, en_name],
            color=(245, 158, 11),
        )
