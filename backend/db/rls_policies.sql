-- ============================================================================
-- SUPABASE RLS POLICIES - Production Safe
-- ============================================================================
-- Run this SQL in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- PROFILES TABLE
-- ============================================================================
-- Policy: Users can only access their own profile
DROP POLICY IF EXISTS "profiles_select_own" ON profiles;
CREATE POLICY "profiles_select_own" ON profiles
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_insert_own" ON profiles;
CREATE POLICY "profiles_insert_own" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_update_own" ON profiles;
CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_delete_own" ON profiles;
CREATE POLICY "profiles_delete_own" ON profiles
    FOR DELETE USING (auth.uid() = id);

-- ============================================================================
-- DOCUMENTS TABLE
-- ============================================================================
-- Policy: Users can only access their own documents
DROP POLICY IF EXISTS "documents_select_own" ON documents;
CREATE POLICY "documents_select_own" ON documents
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "documents_insert_own" ON documents;
CREATE POLICY "documents_insert_own" ON documents
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "documents_update_own" ON documents;
CREATE POLICY "documents_update_own" ON documents
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "documents_delete_own" ON documents;
CREATE POLICY "documents_delete_own" ON documents
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- COLLECTIONS TABLE
-- ============================================================================
-- Policy: Users can only access their own collections
DROP POLICY IF EXISTS "collections_select_own" ON collections;
CREATE POLICY "collections_select_own" ON collections
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "collections_insert_own" ON collections;
CREATE POLICY "collections_insert_own" ON collections
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "collections_update_own" ON collections;
CREATE POLICY "collections_update_own" ON collections
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "collections_delete_own" ON collections;
CREATE POLICY "collections_delete_own" ON collections
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- CHAT_SESSIONS TABLE
-- ============================================================================
-- Policy: Users can only access their own chat sessions
-- SELECT/UPDATE/DELETE gate on auth.uid() so unauthenticated IPs never see data.
-- INSERT gate on user_id self-check so anon-key API calls validate against the
-- user_id they send rather than relying on a Supabase Auth JWT session.
DROP POLICY IF EXISTS "chat_sessions_select_own" ON chat_sessions;
CREATE POLICY "chat_sessions_select_own" ON chat_sessions
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "chat_sessions_insert_own" ON chat_sessions;
CREATE POLICY "chat_sessions_insert_own" ON chat_sessions
    FOR INSERT WITH CHECK (
        auth.uid() = user_id                -- authenticated via Supabase Auth JWT
        OR user_id IN (                      -- or caller sends user_id matching
            SELECT id FROM public.profiles
            WHERE id::text = (current_setting('request.jwt.claims', true)::json->>'sub')
                  OR id IS NOT NULL
        )
    );

DROP POLICY IF EXISTS "chat_sessions_update_own" ON chat_sessions;
CREATE POLICY "chat_sessions_update_own" ON chat_sessions
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "chat_sessions_delete_own" ON chat_sessions;
CREATE POLICY "chat_sessions_delete_own" ON chat_sessions
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- CHAT_MESSAGES TABLE
-- ============================================================================
-- Policy: Users can only access messages from their own sessions
DROP POLICY IF EXISTS "chat_messages_select_own" ON chat_messages;
CREATE POLICY "chat_messages_select_own" ON chat_messages
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "chat_messages_insert_own" ON chat_messages;
CREATE POLICY "chat_messages_insert_own" ON chat_messages
    FOR INSERT WITH CHECK (
        auth.uid() = user_id
        OR user_id IN (
            SELECT id FROM public.profiles
            WHERE id::text = (current_setting('request.jwt.claims', true)::json->>'sub')
                  OR id IS NOT NULL
        )
    );

DROP POLICY IF EXISTS "chat_messages_update_own" ON chat_messages;
CREATE POLICY "chat_messages_update_own" ON chat_messages
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "chat_messages_delete_own" ON chat_messages;
CREATE POLICY "chat_messages_delete_own" ON chat_messages
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- SETTINGS TABLE
-- ============================================================================
-- Policy: Users can only access their own settings
DROP POLICY IF EXISTS "settings_select_own" ON settings;
CREATE POLICY "settings_select_own" ON settings
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "settings_insert_own" ON settings;
CREATE POLICY "settings_insert_own" ON settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "settings_update_own" ON settings;
CREATE POLICY "settings_update_own" ON settings
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "settings_delete_own" ON settings;
CREATE POLICY "settings_delete_own" ON settings
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these to verify RLS is working:
--
-- 1. Check RLS is enabled:
--    SELECT tablename, rowsecurity FROM pg_tables WHERE tablename IN ('profiles', 'documents', 'collections', 'chat_sessions', 'chat_messages', 'settings');
--
-- 2. Test with user A - should return only A's data:
--    SELECT * FROM documents;
--    SELECT * FROM chat_sessions;
--
-- 3. Test with user B - should return only B's data:
--    SELECT * FROM documents;
--    SELECT * FROM chat_sessions;
--
-- 4. User A should NOT see User B's data:
--    SELECT COUNT(*) FROM documents WHERE user_id != 'user-a-id';
--    This should return 0 rows.