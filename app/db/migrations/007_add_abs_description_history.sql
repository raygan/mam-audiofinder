-- Add ABS metadata columns to history table for description and future extensibility
ALTER TABLE history ADD COLUMN abs_description TEXT;
ALTER TABLE history ADD COLUMN abs_description_source TEXT;
ALTER TABLE history ADD COLUMN abs_metadata TEXT;
