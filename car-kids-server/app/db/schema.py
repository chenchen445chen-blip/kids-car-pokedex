import sqlite3


SCHEMA_SQL = """
-- 5.2.1 车辆类型分类表
CREATE TABLE IF NOT EXISTS vehicle_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_id INTEGER NULL REFERENCES vehicle_categories(id) ON DELETE SET NULL,
    icon_image_id INTEGER NULL,
    description TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON vehicle_categories(parent_id, is_active, sort_order);

-- 5.2.2 品牌/子品牌表
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    brand_group TEXT NOT NULL DEFAULT 'china_independent',
    manufacturer_group TEXT NULL,
    country TEXT NULL,
    logo_image_id INTEGER NULL,
    slogan_child TEXT NULL,
    introduction_child TEXT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_brands_status ON brands(review_status, is_active, sort_order);
CREATE INDEX IF NOT EXISTS idx_brands_group ON brands(brand_group, review_status, is_active);

-- 5.2.3 品牌别名表
CREATE TABLE IF NOT EXISTS brand_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    language TEXT NULL,
    source TEXT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved'
);
CREATE INDEX IF NOT EXISTS idx_brand_aliases_norm ON brand_aliases(normalized_alias, review_status);

-- 5.2.4 产品线/车系表
CREATE TABLE IF NOT EXISTS vehicle_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    parent_series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    code TEXT NULL UNIQUE,
    name TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    series_type TEXT NOT NULL DEFAULT 'vehicle_series',
    body_type_label TEXT NULL,
    introduction_child TEXT NULL,
    cover_image_id INTEGER NULL,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_provider TEXT NULL,
    reviewed_by TEXT NULL,
    reviewed_at TEXT NULL,
    review_note TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_series_brand ON vehicle_series(brand_id, review_status, is_active, sort_order);

-- 5.2.5 车系别名表
CREATE TABLE IF NOT EXISTS vehicle_series_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL REFERENCES vehicle_series(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    language TEXT NULL,
    source TEXT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved'
);
CREATE INDEX IF NOT EXISTS idx_series_aliases_norm ON vehicle_series_aliases(normalized_alias, review_status);

-- 5.2.6 具体车型/年款主表
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    brand_name_raw TEXT NULL,
    series_name_raw TEXT NULL,
    primary_category_id INTEGER NULL REFERENCES vehicle_categories(id) ON DELETE SET NULL,
    model_name TEXT NOT NULL,
    model_name_zh TEXT NULL,
    trim_name TEXT NULL,
    generation TEXT NULL,
    model_year INTEGER NULL,
    body_style TEXT NULL,
    power_type TEXT NULL,
    introduction_child TEXT NULL,
    introduction_parent TEXT NULL,
    recognition_features TEXT NULL,
    usage_description TEXT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_provider TEXT NULL,
    source_recognition_id INTEGER NULL,
    recognition_confidence REAL NULL,
    dedupe_key TEXT NULL UNIQUE,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    is_active INTEGER NOT NULL DEFAULT 1,
    reviewed_by TEXT NULL,
    reviewed_at TEXT NULL,
    review_note TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(review_status, is_active);
CREATE INDEX IF NOT EXISTS idx_vehicles_brand_series ON vehicles(brand_id, series_id, review_status, is_active);

-- 5.2.7 车型与车辆类型分类多对多关联表
CREATE TABLE IF NOT EXISTS vehicle_category_relations (
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES vehicle_categories(id) ON DELETE CASCADE,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (vehicle_id, category_id)
);
CREATE INDEX IF NOT EXISTS idx_vcr_category ON vehicle_category_relations(category_id, vehicle_id);

-- 5.2.8 具体车型别名表
CREATE TABLE IF NOT EXISTS vehicle_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    language TEXT NULL,
    source TEXT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved'
);
CREATE INDEX IF NOT EXISTS idx_vehicle_aliases_norm ON vehicle_aliases(normalized_alias, review_status);

-- 5.2.9 车辆/品牌/车系图片表
CREATE TABLE IF NOT EXISTS vehicle_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    image_type TEXT NOT NULL DEFAULT 'real_photo',
    relative_path TEXT NOT NULL,
    thumbnail_path TEXT NULL,
    mime_type TEXT NOT NULL DEFAULT 'image/png',
    width INTEGER NOT NULL DEFAULT 800,
    height INTEGER NOT NULL DEFAULT 600,
    file_size INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    source_name TEXT NULL,
    source_url TEXT NULL,
    license_info TEXT NULL,
    attribution TEXT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved',
    is_primary INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_vehicle ON vehicle_images(vehicle_id, review_status, is_primary, sort_order);
CREATE INDEX IF NOT EXISTS idx_images_series ON vehicle_images(series_id, review_status, is_primary, sort_order);
CREATE INDEX IF NOT EXISTS idx_images_brand ON vehicle_images(brand_id, review_status, is_primary);

-- 5.2.10 识别记录表
CREATE TABLE IF NOT EXISTS recognition_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    provider_name TEXT NOT NULL,
    result_status TEXT NOT NULL,
    matched_brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    matched_series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    matched_vehicle_id INTEGER NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    created_brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    created_series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    created_vehicle_id INTEGER NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    confidence REAL NULL,
    raw_result_json TEXT NULL,
    image_retained INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 5.2.11 识别候选表
CREATE TABLE IF NOT EXISTS recognition_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recognition_record_id INTEGER NOT NULL REFERENCES recognition_records(id) ON DELETE CASCADE,
    brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    vehicle_id INTEGER NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    raw_brand_name TEXT NULL,
    raw_series_name TEXT NULL,
    raw_model_name TEXT NULL,
    raw_category_name TEXT NULL,
    confidence REAL NULL,
    rank INTEGER NOT NULL DEFAULT 1
);

-- 5.2.12 信息不足的识别待处理记录表
CREATE TABLE IF NOT EXISTS recognition_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recognition_record_id INTEGER NOT NULL REFERENCES recognition_records(id) ON DELETE CASCADE,
    raw_result_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_brand_id INTEGER NULL REFERENCES brands(id) ON DELETE SET NULL,
    resolved_series_id INTEGER NULL REFERENCES vehicle_series(id) ON DELETE SET NULL,
    resolved_vehicle_id INTEGER NULL REFERENCES vehicles(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 5.2.13 管理审核日志表
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT 'admin',
    summary TEXT NULL,
    created_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)

