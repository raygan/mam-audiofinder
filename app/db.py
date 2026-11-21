"""SQLite storage (/data/history.db) with versioned migrations.

Add a migration by appending to MIGRATIONS; never edit or reorder an
existing one. Each step is SQL text or a callable taking a connection, and
each migration runs in its own transaction with its version recorded in
schema_version.
"""
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

# /data should be a volume/bind mount
DB_PATH = os.getenv("APP_DB_PATH", "/data/history.db")
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _columns(cx, table: str) -> set[str]:
    return {row[1] for row in cx.execute(text(f"PRAGMA table_info({table})"))}


def _baseline(cx):
    # Databases from before versioned migrations may already have the table,
    # with or without the later columns, so add only what's missing.
    cx.execute(text("""
        CREATE TABLE IF NOT EXISTS history (
          id INTEGER PRIMARY KEY,
          mam_id   TEXT,
          title    TEXT,
          dl       TEXT,
          added_at TEXT DEFAULT (datetime('now')),
          qb_status TEXT,
          qb_hash   TEXT
        )
    """))
    have = _columns(cx, "history")
    for col in ("author", "narrator", "imported_at"):
        if col not in have:
            cx.execute(text(f"ALTER TABLE history ADD COLUMN {col} TEXT"))


MIGRATIONS = [
    (1, [_baseline]),
    (2, ["CREATE INDEX IF NOT EXISTS idx_history_mam_id ON history (mam_id)"]),
]


def schema_version(cx) -> int:
    cx.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"))
    v = cx.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
    return int(v or 0)


def migrate(eng=None) -> int:
    """Apply pending migrations in order. Returns the resulting version."""
    eng = eng or engine
    with eng.begin() as cx:
        current = schema_version(cx)
    for version, steps in MIGRATIONS:
        if version <= current:
            continue
        with eng.begin() as cx:
            for step in steps:
                if callable(step):
                    step(cx)
                else:
                    cx.execute(text(step))
            cx.execute(text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": version})
        current = version
    return current


# ---------------------------- history ----------------------------
def record_history(mam_id: str, title: str, author: str, narrator: str, dl: str, qb_hash: str | None):
    with engine.begin() as cx:
        cx.execute(text("""
            INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at)
            VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at)
        """), {
            "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
            "dl": dl, "qb_status": "added", "qb_hash": qb_hash, "added_at": utc_now(),
        })


def list_history(limit: int = 200) -> list[dict]:
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status
            FROM history
            ORDER BY id DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def delete_history(row_id: int):
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})


def mark_imported(history_id: int | None, qb_hash: str):
    with engine.begin() as cx:
        if history_id is not None:
            cx.execute(text("UPDATE history SET qb_status='imported', imported_at=:ts WHERE id=:id"),
                       {"ts": utc_now(), "id": history_id})
        else:
            # Fallback: try by torrent hash if we have it
            cx.execute(text("UPDATE history SET qb_status='imported', imported_at=:ts WHERE qb_hash=:h"),
                       {"ts": utc_now(), "h": qb_hash})
