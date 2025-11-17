-- Create torrent_books junction table for multi-book imports
-- Enables one torrent to map to multiple books/history entries
CREATE TABLE IF NOT EXISTS torrent_books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_hash TEXT NOT NULL,           -- qBittorrent torrent hash
    history_id INTEGER NOT NULL,          -- Link to history table (primary entry for torrent)
    position INTEGER,                     -- Book position in series (optional)
    subdirectory TEXT,                    -- Relative path within torrent root
    book_title TEXT,                      -- Book title for easy reference
    book_author TEXT,                     -- Book author for easy reference
    series_name TEXT,                     -- Series name if part of a series
    imported_at TEXT DEFAULT (datetime('now')),
    abs_item_id TEXT,                     -- Audiobookshelf library item ID
    abs_verify_status TEXT,               -- Verification status: verified, mismatch, not_found, etc.
    abs_verify_note TEXT,                 -- Additional verification details
    FOREIGN KEY(history_id) REFERENCES history(id) ON DELETE CASCADE
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_torrent_books_hash ON torrent_books(torrent_hash);
CREATE INDEX IF NOT EXISTS idx_torrent_books_history ON torrent_books(history_id);
CREATE INDEX IF NOT EXISTS idx_torrent_books_abs_item ON torrent_books(abs_item_id);
