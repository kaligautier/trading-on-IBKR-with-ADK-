-- Apply to the existing normalized scanner database before deploying the v2 writer.
-- Existing rows and legacy text columns are preserved; report=NULL identifies v1.
BEGIN;
ALTER TABLE market_scans ADD COLUMN IF NOT EXISTS report JSONB;
ALTER TABLE market_scans ALTER COLUMN recommendation DROP NOT NULL;
ALTER TABLE market_scan_assets ALTER COLUMN trend DROP NOT NULL;
COMMIT;
