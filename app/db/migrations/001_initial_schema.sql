-- Initial history table schema
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    mam_id   TEXT,
    title    TEXT,
    dl       TEXT,
    added_at TEXT DEFAULT (datetime('now')),
    qb_status TEXT,
    qb_hash   TEXT
);
