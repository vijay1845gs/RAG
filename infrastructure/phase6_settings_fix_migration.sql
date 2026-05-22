-- ================================================================
-- Phase 6 FIX: Add missing columns to existing settings table
-- Run this in Supabase SQL Editor if you already ran the first migration
-- but columns like auto_scroll are missing.
-- ================================================================

-- Add missing columns (IF NOT EXISTS to be safe)
ALTER TABLE public.settings
  ADD COLUMN IF NOT EXISTS auto_scroll             boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS show_sources            boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS save_chat_history       boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS default_upload_collection uuid NULL,
  ADD COLUMN IF NOT EXISTS rag_mode                text NOT NULL DEFAULT 'balanced',
  ADD COLUMN IF NOT EXISTS response_style          text NOT NULL DEFAULT 'professional',
  ADD COLUMN IF NOT EXISTS default_collection_id   uuid NULL,
  ADD COLUMN IF NOT EXISTS preferred_model         text NOT NULL DEFAULT 'gemini',
  ADD COLUMN IF NOT EXISTS temperature             float NOT NULL DEFAULT 0.3,
  ADD COLUMN IF NOT EXISTS max_context_chunks      integer NOT NULL DEFAULT 5,
  ADD COLUMN IF NOT EXISTS chunk_size              integer NOT NULL DEFAULT 1000,
  ADD COLUMN IF NOT EXISTS chunk_overlap           integer NOT NULL DEFAULT 200,
  ADD COLUMN IF NOT EXISTS theme                   text NOT NULL DEFAULT 'dark',
  ADD COLUMN IF NOT EXISTS updated_at              timestamptz NOT NULL DEFAULT now();

-- Add constraints if they don't exist (ignore errors if they already do)
DO $$
BEGIN
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_temperature_range CHECK (temperature >= 0.0 AND temperature <= 2.0);
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_max_context_chunks_range CHECK (max_context_chunks >= 1 AND max_context_chunks <= 20);
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_chunk_size_range CHECK (chunk_size >= 200 AND chunk_size <= 4000);
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_chunk_overlap_valid CHECK (chunk_overlap >= 0 AND chunk_overlap < chunk_size);
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_theme_valid CHECK (theme IN ('dark', 'light', 'system'));
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_rag_mode_valid CHECK (rag_mode IN ('precise', 'balanced', 'creative'));
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_response_style_valid CHECK (
      response_style IN ('professional', 'concise', 'beginner_friendly', 'research', 'technical')
    );
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
  BEGIN
    ALTER TABLE public.settings ADD CONSTRAINT settings_preferred_model_valid CHECK (
      preferred_model IN ('gemini', 'gpt', 'claude', 'local')
    );
  EXCEPTION WHEN duplicate_object THEN NULL;
  END;
END $$;

-- Enable RLS if not already enabled
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

-- RLS policy (ignore if exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'settings' AND policyname = 'Users can read own settings'
  ) THEN
    CREATE POLICY "Users can read own settings" ON public.settings FOR SELECT USING (auth.uid() = user_id);
  END IF;
END $$;

-- Index
CREATE INDEX IF NOT EXISTS settings_user_id_idx ON public.settings(user_id);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION public.update_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS settings_updated_at_trigger ON public.settings;
CREATE TRIGGER settings_updated_at_trigger
  BEFORE UPDATE ON public.settings
  FOR EACH ROW EXECUTE FUNCTION public.update_settings_updated_at();

SELECT 'Migration complete. Columns added successfully.' as status;
