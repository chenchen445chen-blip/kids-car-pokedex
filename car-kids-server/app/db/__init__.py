from app.db.database import db_session, ensure_directories, get_connection, normalize_text, utc_now_iso
from app.db.schema import init_schema
from app.db.seed import seed_initial_data


def initialize_database() -> None:
    ensure_directories()
    with db_session() as conn:
        init_schema(conn)
        seed_initial_data(conn)


__all__ = [
    "db_session",
    "ensure_directories",
    "get_connection",
    "normalize_text",
    "utc_now_iso",
    "initialize_database",
]

