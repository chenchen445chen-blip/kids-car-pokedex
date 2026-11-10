import sqlite3
from typing import Optional

from app.db.database import normalize_text


def match_brand(
    conn: sqlite3.Connection,
    brand_name: Optional[str],
    brand_name_zh: Optional[str],
) -> Optional[sqlite3.Row]:
    """第 1 级匹配：在已审核品牌及品牌别名中查找匹配的品牌。"""
    candidates_raw = [b for b in [brand_name_zh, brand_name] if b and b.strip()]
    for raw in candidates_raw:
        norm = normalize_text(raw)
        if not norm:
            continue
        row = conn.execute(
            """
            SELECT b.*
            FROM brands b
            WHERE b.review_status = 'approved'
              AND b.is_active = 1
              AND (
                  LOWER(REPLACE(b.name_zh, ' ', '')) = ?
                  OR LOWER(REPLACE(b.name, ' ', '')) = ?
                  OR EXISTS (
                      SELECT 1 FROM brand_aliases ba
                      WHERE ba.brand_id = b.id
                        AND ba.review_status = 'approved'
                        AND ba.normalized_alias = ?
                  )
              )
            LIMIT 1
            """,
            (norm, norm, norm),
        ).fetchone()
        if row:
            return row
    return None


def match_series(
    conn: sqlite3.Connection,
    brand_id: int,
    series_name: Optional[str],
    series_name_zh: Optional[str],
) -> list[sqlite3.Row]:
    """第 2 级匹配：在已匹配的品牌范围内匹配已审核车系及车系别名。"""
    candidates_raw = [s for s in [series_name_zh, series_name] if s and s.strip()]
    matched: dict[int, sqlite3.Row] = {}
    for raw in candidates_raw:
        norm = normalize_text(raw)
        if not norm:
            continue
        rows = conn.execute(
            """
            SELECT s.*
            FROM vehicle_series s
            WHERE s.brand_id = ?
              AND s.series_type = 'vehicle_series'
              AND s.review_status = 'approved'
              AND s.is_active = 1
              AND (
                  LOWER(REPLACE(s.name_zh, ' ', '')) = ?
                  OR LOWER(REPLACE(s.name, ' ', '')) = ?
                  OR EXISTS (
                      SELECT 1 FROM vehicle_series_aliases sa
                      WHERE sa.series_id = s.id
                        AND sa.review_status = 'approved'
                        AND sa.normalized_alias = ?
                  )
              )
            """,
            (brand_id, norm, norm, norm),
        ).fetchall()
        for r in rows:
            matched[r["id"]] = r
    return list(matched.values())


def match_vehicle_under_series(
    conn: sqlite3.Connection,
    series_id: int,
    model_name: Optional[str],
    trim_name: Optional[str] = None,
    model_year: Optional[int] = None,
) -> list[sqlite3.Row]:
    """
    第 3 级匹配：在已命中的车系下匹配具体车型/配置。
    严格遵守规则：若 AI 只返回车系而 model_name 为空，绝不将车系强行下推到某个具体配置。
    """
    if not model_name or not model_name.strip():
        return []

    norm_model = normalize_text(model_name)
    rows = conn.execute(
        """
        SELECT v.*
        FROM vehicles v
        WHERE v.series_id = ?
          AND v.review_status = 'approved'
          AND v.is_active = 1
          AND (
              LOWER(REPLACE(v.model_name, ' ', '')) = ?
              OR LOWER(REPLACE(COALESCE(v.model_name_zh, ''), ' ', '')) = ?
              OR EXISTS (
                  SELECT 1 FROM vehicle_aliases va
                  WHERE va.vehicle_id = v.id
                    AND va.review_status = 'approved'
                    AND va.normalized_alias = ?
              )
          )
        """,
        (series_id, norm_model, norm_model, norm_model),
    ).fetchall()

    if len(rows) > 1 and model_year:
        year_filtered = [r for r in rows if r["model_year"] == model_year]
        if year_filtered:
            return year_filtered

    return rows


def match_category_by_name(
    conn: sqlite3.Connection, category_name: Optional[str]
) -> Optional[int]:
    if not category_name or not category_name.strip():
        return None
    norm = category_name.strip()
    row = conn.execute(
        """
        SELECT id FROM vehicle_categories
        WHERE is_active = 1 AND (name = ? OR code = ?)
        LIMIT 1
        """,
        (norm, norm.lower()),
    ).fetchone()
    return int(row["id"]) if row else None

