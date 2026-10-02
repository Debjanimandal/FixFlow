-- PatchR Schema Migration
-- Run this in your Supabase SQL editor or against your PostgreSQL database.
-- Safe to run multiple times (uses IF NOT EXISTS / DO blocks).

-- ── 1. Add retry_count to incidents ──────────────────────────────────────────
ALTER TABLE incidents
  ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;

-- ── 2. Add human_review_required to incidentstatus enum ──────────────────────
DO 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_enum
    WHERE enumlabel = 'human_review_required'
      AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'incidentstatus')
  ) THEN
    ALTER TYPE incidentstatus ADD VALUE 'human_review_required'
      AFTER 'awaiting_review';
  END IF;
END ;

-- ── 3. Ensure duration_seconds on verification_results (may already exist) ───
ALTER TABLE verification_results
  ADD COLUMN IF NOT EXISTS duration_seconds FLOAT;

-- ── 4. Add verification_type to verification_results (for distinguishing
--       static_analysis vs build_validation rows) ────────────────────────────
ALTER TABLE verification_results
  ADD COLUMN IF NOT EXISTS verification_type VARCHAR(64) NOT NULL DEFAULT 'static_analysis';

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('incidents', 'verification_results')
  AND column_name IN ('retry_count', 'duration_seconds', 'verification_type')
ORDER BY table_name, column_name;
