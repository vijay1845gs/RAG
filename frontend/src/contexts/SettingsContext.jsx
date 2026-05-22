import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react'
import { fetchSettings, updateSettings, resetSettings } from '../services/api'
import { useAuth } from './AuthContext'

const SettingsContext = createContext(null)

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within <SettingsProvider>')
  return ctx
}

/* ─── Factory defaults (mirrors backend DEFAULT_SETTINGS) ─────── */
export const FACTORY_DEFAULTS = {
  theme: 'dark',
  default_collection_id: null,
  preferred_model: 'gemini',
  temperature: 0.3,
  max_context_chunks: 5,
  chunk_size: 1000,
  chunk_overlap: 200,
  auto_scroll: true,
  show_sources: true,
  save_chat_history: true,
  default_upload_collection: null,
  rag_mode: 'balanced',
  response_style: 'professional',
}

const DEBOUNCE_MS = 800

function normalizeSettings(data) {
  if (!data) return FACTORY_DEFAULTS
  const defaultCollection =
    data.default_collection_id ??
    (data.default_collection === 'default' ? null : data.default_collection) ??
    FACTORY_DEFAULTS.default_collection_id

  return {
    ...FACTORY_DEFAULTS,
    ...data,
    default_collection_id: defaultCollection,
    max_context_chunks:
      data.max_context_chunks ?? data.top_k ?? FACTORY_DEFAULTS.max_context_chunks,
    preferred_model:
      data.preferred_model ?? data.model_name ?? FACTORY_DEFAULTS.preferred_model,
  }
}

export function SettingsProvider({ children }) {
  const { user, isAuthenticated } = useAuth()
  const [settings, setSettings] = useState(FACTORY_DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null) // null | 'saving' | 'saved' | 'error'
  const debounceRef = useRef(null)
  const pendingRef = useRef(null)

  /* ─── Load from backend when user logs in ─────────────────── */
  useEffect(() => {
    if (!isAuthenticated || !user?.id) {
      setSettings(FACTORY_DEFAULTS)
      return
    }
    setLoading(true)
    fetchSettings(user.id)
      .then(({ data }) => {
        if (data) {
          setSettings(prev => ({ ...prev, ...normalizeSettings(data) }))
        }
      })
      .catch(() => {
        // Fall back to factory defaults on network error
        setSettings(FACTORY_DEFAULTS)
      })
      .finally(() => setLoading(false))
  }, [user?.id, isAuthenticated])

  useEffect(() => {
    const root = document.documentElement
    const preferredTheme = settings.theme || 'dark'
    const systemTheme = window.matchMedia?.('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark'
    const resolvedTheme = preferredTheme === 'system' ? systemTheme : preferredTheme

    root.dataset.theme = resolvedTheme
    root.style.colorScheme = resolvedTheme
  }, [settings.theme])

  /* ─── Debounced save to backend ───────────────────────────── */
  const _flushSave = useCallback(async (patch) => {
    if (!user?.id || !patch || Object.keys(patch).length === 0) return
    setSaveStatus('saving')
    setSaving(true)
    try {
      const { data } = await updateSettings(user.id, patch)
      if (data) setSettings(prev => ({ ...prev, ...normalizeSettings(data) }))
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(null), 2500)
    } catch {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus(null), 3000)
    } finally {
      setSaving(false)
      pendingRef.current = null
    }
  }, [user?.id])

  /* ─── Public: update one or many settings fields ──────────── */
  const update = useCallback((patch) => {
    // Optimistic update immediately
    setSettings(prev => ({ ...prev, ...patch }))
    setSaveStatus('saving')

    // Accumulate pending changes
    pendingRef.current = { ...(pendingRef.current || {}), ...patch }

    // Debounce the network write
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      _flushSave(pendingRef.current)
    }, DEBOUNCE_MS)
  }, [_flushSave])

  /* ─── Public: force-save immediately (e.g. on blur) ──────── */
  const saveNow = useCallback(async (patch) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const toSave = patch || pendingRef.current
    if (toSave) await _flushSave(toSave)
  }, [_flushSave])

  /* ─── Public: reset to factory defaults ──────────────────── */
  const reset = useCallback(async () => {
    if (!user?.id) return
    setSaveStatus('saving')
    try {
      const { data } = await resetSettings(user.id)
      if (data) setSettings(prev => ({ ...prev, ...normalizeSettings(data) }))
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(null), 2500)
    } catch {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus(null), 3000)
    }
  }, [user?.id])

  const value = useMemo(() => ({
    settings,
    loading,
    saving,
    saveStatus,
    update,
    saveNow,
    reset,
  }), [settings, loading, saving, saveStatus, update, saveNow, reset])

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  )
}
