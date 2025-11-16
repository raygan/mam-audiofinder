-- Add Audiobookshelf verification columns to history table
-- These columns track whether imported items successfully appear in ABS

-- Verification status: 'verified', 'mismatch', 'pending', 'unreachable', or NULL
ALTER TABLE history ADD COLUMN abs_verify_status TEXT;

-- Diagnostic message: "Title mismatch: expected 'X' found 'Y'" or "Not found in library"
ALTER TABLE history ADD COLUMN abs_verify_note TEXT;
