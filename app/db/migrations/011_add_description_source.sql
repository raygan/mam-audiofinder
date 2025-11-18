-- Migration 011: Add description source tracking to covers table
-- Tracks which API provided the description (abs, hardcover, etc.)

-- Add description_source column to track which API provided the description
ALTER TABLE covers ADD COLUMN description_source TEXT;
-- Possible values: 'abs', 'hardcover', NULL

-- Update existing rows to mark source as 'abs' if description exists
UPDATE covers
SET description_source = 'abs'
WHERE abs_description IS NOT NULL AND abs_description != '';
