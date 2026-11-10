import sqlite3
from typing import Optional

from app.services.image_service import build_image_url


def list_categories(
    conn: sqlite3.Connection,
    parent_id: Optional[int] = None,
    include_count: bool = True,
    tree: bool = True,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.code,
            c.name,
            c.parent_id,
            c.icon_image_id,
            c.description,
            c.sort_order,
            (
                SELECT COUNT(DISTINCT v.id)
                FROM vehicle_category_relations vcr
                JOIN vehicles v ON v.id = vcr.vehicle_id
                WHERE vcr.category_id = c.id
                  AND v.review_status = 'approved'
                  AND v.is_active = 1
            ) AS vehicle_count
        FROM vehicle_categories c
        WHERE c.is_active = 1
        ORDER BY c.sort_order ASC, c.id ASC
        """
    ).fetchall()

    items = [
        {
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "parent_id": r["parent_id"],
            "icon_url": build_image_url(r["icon_image_id"]),
            "description": r["description"],
            "sort_order": r["sort_order"],
            "vehicle_count": r["vehicle_count"] if include_count else None,
            "children": [],
        }
        for r in rows
    ]

    if parent_id is not None:
        return [item for item in items if item["parent_id"] == parent_id]

    if not tree:
        return items

    by_id = {item["id"]: item for item in items}
    roots: list[dict] = []
    for item in items:
        pid = item["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(item)
        else:
            roots.append(item)
    return roots

