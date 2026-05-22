-- ══════════════════════════════════════════════════════════════════════════════════════
-- RAG Supabase Schema
--
-- How to apply:
--   1. Open your Supabase project Dashboard
--   2. Go to SQL Editor → New Query
--   3. Paste the full contents of this file
--   4. Press Run
--
-- Required Supabase enablements (Settings → Auth/Storage):
--   ✓ Enable Row Level Security (RLS) — handled per-table below
--   ✓ Auth module enabled  (default in every new Supabase project)
--   ✓ Realtime / Storage left for a later phase
-- ──────────────────────────────────────────────────────────────────────────────────
-- Supabase query history safe: all DROP POLICY / DROP TRIGGER calls are
-- scoped to the objects they create, so applying this file twice is idempotent.

-- ─── Extension ───────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Helper function ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 1  profiles
-- Extends Supabase auth.users with display name + avatar
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.profiles (
  id         UUID       PRIMARY KEY REFERENCES auth.users(id)  ON DELETE CASCADE,
  email      TEXT       NOT NULL,
  full_name  TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profiles_own_read"   ON public.profiles;
DROP POLICY IF EXISTS "profiles_own_insert" ON public.profiles;
DROP POLICY IF EXISTS "profiles_own_update" ON public.profiles;

CREATE POLICY "profiles_own_read"   ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_own_insert" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_own_update" ON public.profiles FOR UPDATE  USING (auth.uid() = id);

DROP TRIGGER  IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER  trg_profiles_updated_at BEFORE UPDATE ON public.profiles
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Auto-create a profile row when a new auth user signs up
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, (NEW.raw_user_meta_data ->> 'full_name')::TEXT)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER  IF EXISTS trg_handle_new_auth_user ON auth.users;
CREATE TRIGGER  trg_handle_new_auth_user
  AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 2  collections
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.collections (
  id          UUID       PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID       NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name        TEXT       NOT NULL,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.collections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "collections_own_crud" ON public.collections;
CREATE POLICY "collections_own_crud" ON public.collections
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_collections_user_id ON public.collections (user_id);

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 3  documents
-- Mirrors the upload result returned by GET/POST /api/v1/upload
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.documents (
  id             UUID       PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id        UUID       NOT NULL REFERENCES public.profiles(id)   ON DELETE CASCADE,
  collection_id  UUID       NOT NULL REFERENCES public.collections(id) ON DELETE CASCADE,
  filename       TEXT       NOT NULL,
  document_id    TEXT       NOT NULL,
  total_pages    INT,
  total_chunks   INT,
  upload_status  TEXT       DEFAULT 'processing' NOT NULL,
  file_size      BIGINT,
  created_at     TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "documents_own_crud" ON public.documents;
CREATE POLICY "documents_own_crud" ON public.documents
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_documents_user_id       ON public.documents (user_id);
CREATE INDEX IF NOT EXISTS idx_documents_collection_id  ON public.documents (collection_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at     ON public.documents (created_at DESC);

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 4  chat_sessions
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id         UUID       PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id TEXT       UNIQUE,
  user_id    UUID       NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  title      TEXT       DEFAULT 'New Chat' NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "chat_sessions_own_crud" ON public.chat_sessions;
CREATE POLICY "chat_sessions_own_crud" ON public.chat_sessions
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id  ON public.chat_sessions (user_id);

DROP TRIGGER  IF EXISTS trg_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER  trg_chat_sessions_updated_at BEFORE UPDATE ON public.chat_sessions
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 5  chat_messages
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.chat_messages (
  id            UUID       PRIMARY KEY DEFAULT uuid_generate_v4(),
  message_id    TEXT       UNIQUE,
  session_id    UUID       NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
  question      TEXT       NOT NULL,
  answer        TEXT       NOT NULL,
  sources_json  JSONB,
  response_time FLOAT,
  created_at    TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "chat_messages_session_owner" ON public.chat_messages;
CREATE POLICY "chat_messages_session_owner" ON public.chat_messages
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.chat_sessions cs
            WHERE cs.id = chat_messages.session_id
              AND cs.user_id = auth.uid())
  );

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON public.chat_messages (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages (created_at DESC);

-- ══════════════════════════════════════════════════════════════════════════════════
-- TABLE 6  settings
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.settings (
  id                 UUID       PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id            UUID       NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE,
  default_collection TEXT      DEFAULT 'default',
  top_k              INT        DEFAULT 5 CHECK (top_k BETWEEN 1 AND 20),
  model_name         TEXT       DEFAULT 'qwen2.5:3b',
  backend_url        TEXT       DEFAULT 'http://localhost:8000',
  theme              TEXT       DEFAULT 'dark' NOT NULL,
  default_collection_id UUID,
  preferred_model    TEXT       DEFAULT 'gemini' NOT NULL,
  temperature        FLOAT      DEFAULT 0.3 NOT NULL,
  max_context_chunks INT        DEFAULT 5 NOT NULL CHECK (max_context_chunks BETWEEN 1 AND 20),
  chunk_size         INT        DEFAULT 1000 NOT NULL,
  chunk_overlap      INT        DEFAULT 200 NOT NULL,
  auto_scroll        BOOLEAN    DEFAULT TRUE NOT NULL,
  show_sources       BOOLEAN    DEFAULT TRUE NOT NULL,
  save_chat_history  BOOLEAN    DEFAULT TRUE NOT NULL,
  default_upload_collection UUID,
  rag_mode           TEXT       DEFAULT 'balanced' NOT NULL,
  response_style     TEXT       DEFAULT 'professional' NOT NULL,
  created_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "settings_own_crud" ON public.settings;
CREATE POLICY "settings_own_crud" ON public.settings
  FOR ALL USING (auth.uid() = user_id);

DROP INDEX IF EXISTS idx_settings_user_id;
CREATE UNIQUE INDEX idx_settings_user_id ON public.settings (user_id);

DROP TRIGGER  IF EXISTS trg_settings_updated_at ON public.settings;
CREATE TRIGGER  trg_settings_updated_at BEFORE UPDATE ON public.settings
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ══════════════════════════════════════════════════════════════════════════════════
-- VIEW  user_documents_view
-- Joins documents + collection name for dashboard lists
-- ══════════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE VIEW public.user_documents_view AS
SELECT
  d.id,
  d.user_id,
  d.collection_id,
  c.name              AS collection_name,
  d.filename,
  d.document_id,
  d.total_pages,
  d.total_chunks,
  d.upload_status,
  d.created_at
FROM public.documents d
LEFT JOIN public.collections c ON c.id = d.collection_id;

-- ══════════════════════════════════════════════════════════════════════════════════
-- SUMMARY
-- ══════════════════════════════════════════════════════════════════════════════════
-- Tables     profiles, collections, documents, chat_sessions, chat_messages, settings
-- View       user_documents_view
-- RLS        ON  — every policy scopes to auth.uid()
-- Triggers   updated_at (profiles, chat_sessions, settings)
--            handle_new_auth_user (auth.users → profiles on signup)
-- Extensions uuid-ossp  (uuid_generate_v4())
-- Indexes    user_id / collection_id on all scoped tables
-- ══════════════════════════════════════════════════════════════════════════════════
