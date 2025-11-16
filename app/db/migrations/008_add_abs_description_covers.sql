-- Add ABS metadata columns to covers table for showcase view and future extensibility
ALTER TABLE covers ADD COLUMN abs_description TEXT;
ALTER TABLE covers ADD COLUMN abs_metadata TEXT;
ALTER TABLE covers ADD COLUMN abs_metadata_fetched_at TEXT;
