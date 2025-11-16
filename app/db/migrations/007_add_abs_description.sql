-- Add ABS metadata columns to history table for description and future extensibility
ALTER TABLE history ADD COLUMN abs_description TEXT;
ALTER TABLE history ADD COLUMN abs_description_source TEXT;
ALTER TABLE history ADD COLUMN abs_metadata TEXT; -- Full ABS item metadata JSON for future use

-- Add ABS metadata columns to covers table for showcase view
ALTER TABLE covers ADD COLUMN abs_description TEXT;
ALTER TABLE covers ADD COLUMN abs_metadata TEXT; -- Full ABS item metadata JSON for future use
ALTER TABLE covers ADD COLUMN abs_metadata_fetched_at TEXT; -- Track when metadata was last fetched
