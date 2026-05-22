-- Phase 7: Async Processing — Supabase Migration
-- Run this in: Supabase Dashboard → SQL Editor → New Query
--
-- Adds processing lifecycle columns to the documents table.
-- Supabase is the SINGLE SOURCE OF TRUTH for document processing state.
-- Redis is used only as the Celery broker and chat cache — never for state.
--
-- Safe to run multiple times (uses IF NOT EXISTS).

-- ─── Add processing lifecycle columns ────────────────────────────────────────

ALTER TABLE public.documents
  ADD COLUMN IF NOT EXISTS processing_status    text    DEFAULT 'queued'  NOT NULL,
  ADD COLUMN IF NOT EXISTS processing_progress  integer DEFAULT 0         NOT NULL,
  ADD COLUMN IF NOT EXISTS processing_stage     text    NULL,
  ADD COLUMN IF NOT EXISTS job_id               text    NULL,
  ADD COLUMN IF NOT EXISTS processing_started_at   timestamptz NULL,
  ADD COLUMN IF NOT EXISTS processing_completed_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS processing_error     text    NULL,
  ADD COLUMN IF NOT EXISTS retry_count          integer DEFAULT 0         NOT NULL;

-- ─── Add constraint for valid statuses ───────────────────────────────────────
-- (Drop first if it exists from a previous run)

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'documents_processing_status_check'
  ) THEN
    ALTER TABLE public.documents
      ADD CONSTRAINT documents_processing_status_check
      CHECK (processing_status IN ('queued', 'processing', 'retrying', 'completed', 'failed'));
  END IF;
END $$;

-- ─── Add indexes for polling queries ─────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_documents_processing_status
  ON public.documents (processing_status);

CREATE INDEX IF NOT EXISTS idx_documents_job_id
  ON public.documents (job_id)
  WHERE job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_user_processing
  ON public.documents (user_id, processing_status);

-- ─── Backfill existing rows ───────────────────────────────────────────────────
-- Existing 'completed' upload_status → processing_status = 'completed'
-- Existing 'processing' upload_status → processing_status = 'completed' (they finished before Phase 7)

UPDATE public.documents
SET processing_status = 'completed',
    processing_progress = 100
WHERE upload_status = 'completed'
  AND processing_status = 'queued';

-- ─── Verification query ───────────────────────────────────────────────────────
-- Run this to confirm the migration was applied:
--
-- SELECT column_name, data_type, column_default, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'documents'
--   AND column_name LIKE 'processing%'
-- ORDER BY column_name;
