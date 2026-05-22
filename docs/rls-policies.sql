-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES FOR RAG APPLICATION
-- =============================================================================
-- Run these SQL statements in your Supabase SQL editor
-- https://supabase.com/dashboard/project/_/sql
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- PROFILES TABLE POLICIES
-- =============================================================================
-- Users can view their own profile
CREATE POLICY "profiles_select_own" 
ON profiles FOR SELECT 
USING (auth.uid() = id);

-- Users can insert their own profile
CREATE POLICY "profiles_insert_own" 
ON profiles FOR INSERT 
WITH CHECK (auth.uid() = id);

-- Users can update their own profile
CREATE POLICY "profiles_update_own" 
ON profiles FOR UPDATE 
USING (auth.uid() = id) 
WITH CHECK (auth.uid() = id);

-- =============================================================================
-- DOCUMENTS TABLE POLICIES
-- =============================================================================
-- Users can view their own documents
CREATE POLICY "documents_select_own" 
ON documents FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own documents
CREATE POLICY "documents_insert_own" 
ON documents FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own documents
CREATE POLICY "documents_update_own" 
ON documents FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own documents
CREATE POLICY "documents_delete_own" 
ON documents FOR DELETE 
USING (auth.uid() = user_id);

-- =============================================================================
-- COLLECTIONS TABLE POLICIES
-- =============================================================================
-- Users can view their own collections
CREATE POLICY "collections_select_own" 
ON collections FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own collections
CREATE POLICY "collections_insert_own" 
ON collections FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own collections
CREATE POLICY "collections_update_own" 
ON collections FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own collections
CREATE POLICY "collections_delete_own" 
ON collections FOR DELETE 
USING (auth.uid() = user_id);

-- =============================================================================
-- CHAT_SESSIONS TABLE POLICIES
-- =============================================================================
-- Users can view their own chat sessions
CREATE POLICY "chat_sessions_select_own" 
ON chat_sessions FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own chat sessions
CREATE POLICY "chat_sessions_insert_own" 
ON chat_sessions FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own chat sessions
CREATE POLICY "chat_sessions_update_own" 
ON chat_sessions FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own chat sessions
CREATE POLICY "chat_sessions_delete_own" 
ON chat_sessions FOR DELETE 
USING (auth.uid() = user_id);

-- =============================================================================
-- CHAT_MESSAGES TABLE POLICIES
-- =============================================================================
-- Users can view their own chat messages
CREATE POLICY "chat_messages_select_own" 
ON chat_messages FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own chat messages
CREATE POLICY "chat_messages_insert_own" 
ON chat_messages FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own chat messages
CREATE POLICY "chat_messages_update_own" 
ON chat_messages FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own chat messages
CREATE POLICY "chat_messages_delete_own" 
ON chat_messages FOR DELETE 
USING (auth.uid() = user_id);

-- =============================================================================
-- SETTINGS TABLE POLICIES
-- =============================================================================
-- Users can view their own settings
CREATE POLICY "settings_select_own" 
ON settings FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own settings
CREATE POLICY "settings_insert_own" 
ON settings FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own settings
CREATE POLICY "settings_update_own" 
ON settings FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own settings
CREATE POLICY "settings_delete_own" 
ON settings FOR DELETE 
USING (auth.uid() = user_id);

-- =============================================================================
-- TABLE SCHEMA (Run this first if tables don't exist)
-- =============================================================================

-- Create profiles table (if not exists)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users NOT NULL,
    email TEXT,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users NOT NULL,
    collection_id TEXT,
    filename TEXT NOT NULL,
    document_id TEXT UNIQUE NOT NULL,
    total_pages INTEGER,
    total_chunks INTEGER,
    upload_status TEXT DEFAULT 'completed',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create collections table
CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create chat_messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions NOT NULL,
    user_id UUID REFERENCES auth.users NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources_json JSONB,
    response_time FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create settings table
CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users NOT NULL,
    default_collection TEXT,
    top_k INTEGER DEFAULT 5,
    model_selection TEXT,
    temperature FLOAT DEFAULT 0.7,
    theme TEXT DEFAULT 'dark',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id);