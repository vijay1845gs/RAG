import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authLoading, setAuthLoading] = useState(false)

  /* ─── Fetch profile from backend ─────────────────────────────────── */
  const fetchProfile = useCallback(async (userId) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/profile/${userId}`)
      if (res.ok) setProfile(await res.json())
      else setProfile(null)
    } catch { setProfile(null) }
  }, [])

  /* ─── Bootstrap session on mount ─────────────────────────────────── */
  useEffect(() => {
    let isMounted = true

   // Get initial session from Supabase first
supabase.auth
  .getSession()
  .then(({ data }) => {
    if (!isMounted) return

    const sess = data.session
    const usr = sess?.user ?? null

    setSession(sess)
    setUser(usr)

    if (usr) {
      fetchProfile(usr.id)
    }

    setLoading(false)
  })
  .catch(() => {
    if (!isMounted) return

    setUser(null)
    setSession(null)
    setProfile(null)
    setLoading(false)
  })

    // Listen for auth changes AFTER initial hydration
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, sess) => {
      // Skip INITIAL_STATE - we already handled that via getSession()
      if (event === 'INITIAL_STATE') return
      setSession(sess)
      if (sess?.user) {
        setUser(sess.user)
        fetchProfile(sess.user.id)
      } else {
        setUser(null)
        setProfile(null)
      }
    })

    return () => {
      isMounted = false
      subscription?.unsubscribe?.()
    }
  }, [fetchProfile])

  /* ─── Authenticate ───────────────────────────────────────────────── */
  const login = useCallback(async (email, password) => {
    setAuthLoading(true)
    try { await supabase.auth.signInWithPassword({ email, password }) }
    finally { setAuthLoading(false) }
  }, [])

  const signup = useCallback(async (email, password, fullName = '') => {
    setAuthLoading(true)
    try {
      await supabase.auth.signUp({
        email, password,
        options: {
          data: { full_name: fullName },
          emailRedirectTo: typeof window !== 'undefined' ? `${window.location.origin}/` : undefined,
        },
      })
    } finally { setAuthLoading(false) }
  }, [])

  const logout = useCallback(async () => {
    try { await supabase.auth.signOut() } catch { /* best-effort */ }
    setUser(null); setSession(null); setProfile(null)
  }, [])

  const value = useMemo(() => ({
    user, session, profile,
    loading,
    authLoading,
    login, signup, logout,
    isAuthenticated: !!user,
  }), [user, session, profile, loading, authLoading, login, signup, logout])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
