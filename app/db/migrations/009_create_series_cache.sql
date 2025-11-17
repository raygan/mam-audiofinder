-- Create series cache table for Hardcover API responses
CREATE TABLE IF NOT EXISTS series_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT UNIQUE NOT NULL,        -- 'search:{hash}' or 'series:{id}'
    cache_type TEXT NOT NULL,               -- 'search' or 'books'

    -- Search cache fields
    query_title TEXT,
    query_author TEXT,
    query_normalized TEXT,

    -- Series cache fields
    series_id INTEGER,
    series_name TEXT,
    series_author TEXT,

    -- Cache data (JSON blob)
    response_data TEXT NOT NULL,

    -- Cache metadata
    cached_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,               -- TTL: calculated from HARDCOVER_CACHE_TTL
    hit_count INTEGER DEFAULT 0
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_series_cache_key ON series_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_series_expires_at ON series_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_series_id ON series_cache(series_id);
CREATE INDEX IF NOT EXISTS idx_series_cache_type ON series_cache(cache_type);

-- Create trigger to auto-cleanup expired cache entries
CREATE TRIGGER IF NOT EXISTS cleanup_expired_series_cache
AFTER INSERT ON series_cache
BEGIN
    DELETE FROM series_cache
    WHERE datetime(expires_at) < datetime('now');
END;
