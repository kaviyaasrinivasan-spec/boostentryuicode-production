-- Add saved_path column for filesystem-based PDF storage
-- Run this on your PostgreSQL server

ALTER TABLE doc_processing_log ADD COLUMN IF NOT EXISTS saved_path VARCHAR(512);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_doc_log_saved_path ON doc_processing_log(saved_path) WHERE saved_path IS NOT NULL;

-- Create the PDF storage directory on the server
-- Run this in Linux shell:
-- mkdir -p /root/boostentry_pdf
-- chmod 755 /root/boostentry_pdf
