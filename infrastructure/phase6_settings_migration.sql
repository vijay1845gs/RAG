-- ================================================================
-- Phase 6: Settings Persistence
-- Run this in the Supabase SQL editor (Dashboard → SQL Editor)
-- ================================================================

-- 1. Create the settings table
CREATE TABLE IF NOT EXISTS public.settings (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 uuid UNIQUE NOT NULL,
  theme                   text NOT NULL DEFAULT 'dark',
  default_collection_id   uuid NULL,
  preferred_model         text NOT NULL DEFAULT 'gemini',
  temperature             float NOT NULL DEFAULT 0.3,
  max_context_chunks      integer NOT NULL DEFAULT 5,
  chunk_size              integer NOT NULL DEFAULT 1000,
  chunk_overlap           integer NOT NULL DEFAULT 200,
  auto_scroll             boolean NOT NULL DEFAULT true,
  show_sources            boolean NOT NULL DEFAULT true,
  save_chat_history       boolean NOT NULL DEFAULT true,
  default_upload_collection uuid NULL,
  rag_mode                text NOT NULL DEFAULT 'balanced',
  response_style          text NOT NULL DEFAULT 'professional',
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 2. Enable Row-Level Security
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

-- 3. RLS Policy: users can only read their own settings
CREATE POLICY "Users can read own settings"
  ON public.settings
  FOR SELECT
  USING (auth.uid() = user_id);

-- 4. Service role bypasses RLS (no policy needed for writes via admin client)

-- 5. Index for fast user lookups
CREATE INDEX IF NOT EXISTS settings_user_id_idx ON public.settings(user_id);

-- 6. Validation constraints
ALTER TABLE public.settings
  ADD CONSTRAINT settings_temperature_range CHECK (temperature >= 0.0 AND temperature <= 2.0),
  ADD CONSTRAINT settings_max_context_chunks_range CHECK (max_context_chunks >= 1 AND max_context_chunks <= 20),
  ADD CONSTRAINT settings_chunk_size_range CHECK (chunk_size >= 200 AND chunk_size <= 4000),
  ADD CONSTRAINT settings_chunk_overlap_valid CHECK (chunk_overlap >= 0 AND chunk_overlap < chunk_size),
  ADD CONSTRAINT settings_theme_valid CHECK (theme IN ('dark', 'light', 'system')),
  ADD CONSTRAINT settings_rag_mode_valid CHECK (rag_mode IN ('precise', 'balanced', 'creative')),
  ADD CONSTRAINT settings_response_style_valid CHECK (
    response_style IN ('professional', 'concise', 'beginner_friendly', 'research', 'technical')
  ),
  ADD CONSTRAINT settings_preferred_model_valid CHECK (
    preferred_model IN ('gemini', 'gpt', 'claude', 'local')
  );

-- 7. Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION public.update_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER settings_updated_at_trigger
  BEFORE UPDATE ON public.settings
  FOR EACH ROW EXECUTE FUNCTION public.update_settings_updated_at();
