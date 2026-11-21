"""Versioned migrations: fresh DBs, pre-migration (v0.6) DBs, idempotence."""
from sqlalchemy import create_engine, text

import db


def cols(eng, table="history"):
    with eng.begin() as cx:
        return {r[1] for r in cx.execute(text(f"PRAGMA table_info({table})"))}


def indexes(eng):
    with eng.begin() as cx:
        return {r[1] for r in cx.execute(text("PRAGMA index_list(history)"))}


def test_fresh_database(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    assert db.migrate(eng) == db.MIGRATIONS[-1][0]
    assert {"id", "mam_id", "title", "author", "narrator", "dl", "added_at",
            "qb_status", "qb_hash", "imported_at"} <= cols(eng)
    assert "idx_history_mam_id" in indexes(eng)


def test_legacy_database_is_upgraded_and_keeps_rows(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    with eng.begin() as cx:  # the original v0.5-era table, before author/narrator/imported_at
        cx.execute(text("""CREATE TABLE history (id INTEGER PRIMARY KEY, mam_id TEXT, title TEXT, dl TEXT,
                           added_at TEXT DEFAULT (datetime('now')), qb_status TEXT, qb_hash TEXT)"""))
        cx.execute(text("INSERT INTO history (mam_id, title) VALUES ('1', 'Old Book')"))
    db.migrate(eng)
    assert {"author", "narrator", "imported_at"} <= cols(eng)
    with eng.begin() as cx:
        assert cx.execute(text("SELECT title FROM history WHERE mam_id='1'")).scalar() == "Old Book"


def test_partially_migrated_v06_database(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    with eng.begin() as cx:  # v0.6 had author/narrator but maybe not imported_at
        cx.execute(text("""CREATE TABLE history (id INTEGER PRIMARY KEY, mam_id TEXT, title TEXT, dl TEXT,
                           added_at TEXT, qb_status TEXT, qb_hash TEXT, author TEXT, narrator TEXT)"""))
    db.migrate(eng)
    assert "imported_at" in cols(eng)


def test_migrate_is_idempotent(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'h.db'}", future=True)
    v = db.migrate(eng)
    assert db.migrate(eng) == v
    with eng.begin() as cx:
        versions = [r[0] for r in cx.execute(text("SELECT version FROM schema_version ORDER BY version"))]
    assert versions == [m[0] for m in db.MIGRATIONS]


def test_migration_versions_are_ordered_and_unique():
    vs = [m[0] for m in db.MIGRATIONS]
    assert vs == sorted(set(vs))
