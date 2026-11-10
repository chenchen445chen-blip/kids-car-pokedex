from contextlib import contextmanager
from datetime import datetime, timezone
import re
import sqlite3
from typing import Generator

from app.core.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    """规范化匹配文本：转小写、去除首尾及中间多余空白与连接符。"""
    if not text:
        return ""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[\s\-_·•/\\]+", "", cleaned)
    return cleaned


def ensure_directories() -> None:
    settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    for sub in ["catalog/originals", "catalog/thumbnails", "catalog/logos", "catalog/models", "temp"]:
        (settings.STORAGE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(str(settings.DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def db_session() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

