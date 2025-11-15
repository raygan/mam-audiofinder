-- Create covers cache table
CREATE TABLE IF NOT EXISTS covers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mam_id TEXT UNIQUE NOT NULL,
    title TEXT,
    author TEXT,
    cover_url TEXT NOT NULL,
    abs_item_id TEXT,
    local_file TEXT,
    file_size INTEGER,
    fetched_at TEXT DEFAULT (datetime('now'))
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_covers_mam_id ON covers(mam_id);
CREATE INDEX IF NOT EXISTS idx_covers_cover_url ON covers(cover_url);
