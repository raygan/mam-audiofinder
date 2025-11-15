-- Add Audiobookshelf integration columns
ALTER TABLE history ADD COLUMN abs_item_id TEXT;
ALTER TABLE history ADD COLUMN abs_cover_url TEXT;
ALTER TABLE history ADD COLUMN abs_cover_cached_at TEXT;
