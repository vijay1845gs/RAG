import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles,
  Send,
  Clock,
  FileText,
  Loader2,
  AlertCircle,
  MessageSquare,
  Hash,
  ChevronDown,
  Folder,
  Plus,
} from 'lucide-react'
import { submitChat, saveChatMessage, createChatSession, fetchChatSession, fetchCollections, createCollection } from '../services/api'
import { useApp } from '../AppContext'
import { useAuth } from '../contexts/AuthContext'
import { useSettings } from '../contexts/SettingsContext'
import { useNavigate, useParams } from 'react-router-dom'

/* colour helper: relevance → tailwind bg class */
const relevanceColor = (score) => {
  const pct = (score ?? 0) * 100
  if (pct >= 80) return 'bg-emerald-500'
  if (pct >= 55) return 'bg-amber-500'
  return 'bg-red-500'
}

const chunkCount = (turn) =>
  turn?.retrieved_chunks ?? turn?.retrieval_count ?? turn?.sources?.length ?? 0

const SHOW_RETRIEVAL_DEBUG = import.meta.env.DEV

/* ═════════════════════════════════════════════════
   CHAT PAGE
══════════════════════════════════════════════════ */
export default function Chat() {
  const { user } = useAuth()
  const { settings } = useSettings()
  const { sessionId: urlSessionId } = useParams()
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [collections, setCollections] = useState([])
  const [collectionsLoading, setCollectionsLoading] = useState(false)
  const [collectionsOpen, setCollectionsOpen] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState('default')

  /* ─── Sync default collection from settings ─── */
  useEffect(() => {
    if (settings?.default_collection_id) {
      setSelectedCollection(settings.default_collection_id)
    } else {
      const saved = localStorage.getItem('chat_selected_collection')
      if (saved) setSelectedCollection(saved)
    }
  }, [settings?.default_collection_id])
  useEffect(() => {
    localStorage.setItem('chat_selected_collection', selectedCollection)
  }, [selectedCollection])

  const defaultObj = { id: 'default', name: 'default', total_documents: 0 }
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState(null)        // null | { answer, response_time, sources }
  const [error, setError] = useState(null)
  const [sessionError, setSessionError] = useState(null)
  const [history, setHistory] = useState([])        // [{ question, answer, response_time, sources }]
  const [expandedSources, setExpandedSources] = useState({})
  const [expandedDebug, setExpandedDebug] = useState({})
  const inputRef = useRef(null)
  const { addChatTurn } = useApp()
  // effectiveSessionId: URL param takes precedence; falls back to 'default' (for new chats)
  const [effectiveSessionId, setEffectiveSessionId] = useState(urlSessionId || 'default')
  const [sessionLoading, setSessionLoading] = useState(false)

  /* ─── submit ─────────────────────────────────────────────── */
  const handleSend = useCallback(async (e) => {
    e?.preventDefault()
    if (!question.trim() || loading) return
    const shouldSaveHistory = settings?.save_chat_history !== false

    // Resolve session: if we already have one (URL or previously created), reuse it;
    // otherwise create a fresh session now so every chat is persisted.
    let session_id = shouldSaveHistory ? effectiveSessionId : 'local'
    if (shouldSaveHistory && (!session_id || session_id === 'default')) {
      try {
        const { data } = await createChatSession(user?.id, 'New Conversation')
        session_id = data?.session_id || session_id
        console.log('[Chat.jsx] New Session ID:', session_id)
        if (session_id === 'default') {
          console.warn('[Chat.jsx] createChatSession did NOT return a UUID; using fallback')
        }
        setEffectiveSessionId(session_id)
      } catch {
        session_id = 'default'
        setEffectiveSessionId('default')
      }
    }

    setLoading(true); setError(null); setAnswer(null)

    // Determine if top_k and temperature are explicit user overrides vs just mode presets.
    // If they match the presets (including the stale legacy balanced preset of 5), 
    // we omit them from the payload so the backend's strict precedence takes over.
    const mode = settings?.rag_mode ?? 'balanced'
    let top_k = settings?.max_context_chunks ?? 5
    let temperature = settings?.temperature ?? 0.3

    const PRESETS = {
      precise: { top_k: 3, temp: 0.1 },
      balanced: { top_k: 3, temp: 0.3 },
      creative: { top_k: 8, temp: 0.8 },
    }
    const STALE_BALANCED = { top_k: 5, temp: 0.3 }

    const preset = PRESETS[mode] || PRESETS.balanced
    const isCurrentPreset = top_k === preset.top_k && temperature === preset.temp
    const isStalePreset = mode === 'balanced' && top_k === STALE_BALANCED.top_k && temperature === STALE_BALANCED.temp

    if (isCurrentPreset || isStalePreset) {
      top_k = undefined
      temperature = undefined
    }

    try {
      const { data } = await submitChat({
        collection_id: (selectedCollection || 'default').trim() || 'default',
        question: question.trim(),
        top_k,
        temperature,
        rag_mode: mode,
        response_style: settings?.response_style ?? 'professional',
        show_sources: settings?.show_sources !== false,
        preferred_model: settings?.preferred_model,
        user_id: user?.id,
      })
      setAnswer(data)
      setHistory((prev) => [...prev, { question: question.trim(), ...data, session_id }])
      if (shouldSaveHistory) {
        addChatTurn({ question: question.trim(), ...data, session_id })
      }

      // Save to backend under the resolved session
      if (shouldSaveHistory && user?.id) {
        await saveChatMessage({
          session_id,
          question: question.trim(),
          answer: data.answer,
          sources_json: {
            retrieved_chunks: data.retrieved_chunks,
            sources: data.sources,
          },
          response_time: data.response_time,
          user_id: user.id,
        })
      }

      setQuestion('')
    } catch (err) {
      setError(err?.response?.data?.error || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [question, selectedCollection, loading, addChatTurn, user?.id, effectiveSessionId, settings])

  /* ─── keyboard: Enter to send ───────────────────────────── */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  /* ─── focus input on mount ──────────────────────────────── */
  useEffect(() => { inputRef.current?.focus() }, [])

  /* ─── load collections for selector ──────────────────────── */
  useEffect(() => {
    if (!user?.id) return
    setCollectionsLoading(true)
    fetchCollections(user.id)
      .then(r => setCollections(Array.isArray(r.data) ? r.data : []))
      .catch(() => setCollections([]))
      .finally(() => setCollectionsLoading(false))
  }, [user?.id])

  /* ─── load existing session messages when a sessionId is in the URL ─── */
  useEffect(() => {
    const sessionId = urlSessionId
    if (!sessionId || !user?.id) {
      setEffectiveSessionId(sessionId || 'default')
      return
    }

    let cancelled = false
    setSessionLoading(true)
    fetchChatSession(sessionId, user.id)
      .then(r => { if (!cancelled) {
        const messages = (r.data && r.data.messages) || []
        setHistory(
          messages.map(m => {
            const rawSources = safeParseSources(m.sources_json)
            let sourcesArray = rawSources
            let parsedChunks = m.retrieved_chunks

            if (rawSources && !Array.isArray(rawSources) && typeof rawSources === 'object') {
              sourcesArray = rawSources.sources || []
              if (rawSources.retrieved_chunks !== undefined) {
                parsedChunks = rawSources.retrieved_chunks
              } else if (rawSources.retrieval_count !== undefined) {
                parsedChunks = rawSources.retrieval_count
              }
            }

            return {
              question: m.question,
              answer: m.answer,
              response_time: m.response_time,
              sources: sourcesArray,
              retrieved_chunks: parsedChunks,
              retrieval_count: m.retrieval_count
            }
          })
        )
        setEffectiveSessionId(sessionId)
        setSessionError(null)
      }})
      .catch(() => { if (!cancelled) {
        setSessionError('This chat session is no longer available. Starting a new chat.')
        setError(null); setHistory([]); setEffectiveSessionId('default')
        setTimeout(() => { setSessionError(null); navigate('/chat') }, 3500)
      }})
      .finally(() => { if (!cancelled) setSessionLoading(false) })

    return () => { cancelled = true }
  }, [urlSessionId, user?.id])

  /* parse `sources_json` from backend safely */
  const safeParseSources = (raw) => {
    if (!raw) return []
    if (typeof raw === 'object') return raw // Handles both arrays and objects native to JSONB
    try { return JSON.parse(raw) } catch { return [] }
  }

  /* ─── toggle source card ────────────────────────────────── */
  const toggleSource = (key) =>
    setExpandedSources((p) => ({ ...p, [key]: !p[key] }))

  const toggleDebug = (key) =>
    setExpandedDebug((p) => ({ ...p, [key]: !p[key] }))

  /* SOURCE CARD — reused in history and current-answer paths */
  const SourceCard = ({ chunk, indexPrefix }) => {
    const key = `${indexPrefix}-${chunk.chunk_id ?? indexPrefix}`
    const open = !!expandedSources[key]
    return (
      <div key={key} className="rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden">
        <button
          onClick={() => toggleSource(key)}
          className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-800 flex-shrink-0">
            <FileText className="h-3.5 w-3.5 text-zinc-400" />
          </div>
          <span className="flex-1 text-sm text-zinc-300 truncate text-left">{chunk.source_file}</span>
          <span className="text-xs text-zinc-500 flex items-center gap-1">
            <Hash className="h-3 w-3" />p.{chunk.page_number}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${relevanceColor(chunk.relevance_score)} text-white/90`}>
            {Math.round((chunk.relevance_score ?? 0) * 100)}%
          </span>
          <ChevronDown className={`h-4 w-4 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-3 pt-0 border-t border-zinc-800/60">
                <p className="text-xs text-zinc-500 mt-2.5">Chunk ID</p>
                <code className="text-xs text-zinc-400 font-mono">{chunk.chunk_id}</code>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  const RetrievalDebug = ({ items, debugKey }) => {
    if (!SHOW_RETRIEVAL_DEBUG || !items?.length) return null

    const open = !!expandedDebug[debugKey]
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden">
        <button
          type="button"
          onClick={() => toggleDebug(debugKey)}
          className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-zinc-800/50 transition-colors"
        >
          <ChevronDown className={`h-4 w-4 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`} />
          <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
            Retrieval Debug ({items.length} chunks)
          </span>
        </button>

        {open && (
          <div className="border-t border-zinc-800/60 divide-y divide-zinc-800/60">
            {items.map((item, idx) => (
              <div key={`${debugKey}-${item.chunk_id ?? idx}`} className="px-4 py-3 space-y-1.5">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
                  <span className="font-medium text-zinc-300">Chunk {idx + 1}</span>
                  <span>Score: {Number(item.score ?? 0).toFixed(4)}</span>
                  <span>Page: {item.page ?? 'unknown'}</span>
                  {item.chunk_index !== null && item.chunk_index !== undefined && (
                    <span>Index: {item.chunk_index}</span>
                  )}
                </div>
                <p className="text-xs text-zinc-500 truncate">
                  Source: <span className="text-zinc-400">{item.source || 'unknown'}</span>
                </p>
                {item.chunk_id && (
                  <p className="text-xs text-zinc-600 truncate">Chunk ID: {item.chunk_id}</p>
                )}
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {item.preview || 'No preview available.'}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  /* ══════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════ */
  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-6">

        {/* ─── Session-loading error toast ──────────────────────── */}
        <AnimatePresence>
          {sessionError && (
            <motion.div
              initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              className="flex items-start gap-3 rounded-lg border border-amber-500/25
                         bg-amber-500/10 px-4 py-3 text-sm text-amber-400"
            >
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{sessionError}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Page header ─────────────────────────────────────── */}
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
            <Sparkles className="h-5 w-5 text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
            <p className="text-zinc-500 text-sm">Ask questions about your uploaded documents</p>
          </div>
        </div>

        {/* ─── Collection selector dropdown ───────────────────────── */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Collection</span>
          <div className="relative">
            <button
              type="button"
              onClick={() => setCollectionsOpen(!collectionsOpen)}
              className="flex items-center gap-2 h-9 w-52 rounded-lg border border-zinc-800 bg-zinc-900/80
                         px-3 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              <Folder className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
              <span className="flex-1 text-left truncate">
                {collectionsLoading
                  ? 'Loading…'
                  : (collections.find(c => c.id === selectedCollection)?.name || 'default')}
              </span>
              <ChevronDown className={`h-3.5 w-3.5 text-zinc-500 transition-transform ${collectionsOpen ? 'rotate-180' : ''}`} />
            </button>

            {collectionsOpen && (
              <>
                {/* backdrop */}
                <div className="fixed inset-0 z-40" onClick={() => setCollectionsOpen(false)} />

                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute z-50 top-full left-0 mt-1.5 w-52 rounded-xl border border-zinc-800
                             bg-zinc-900 shadow-xl shadow-black/40 overflow-hidden"
                >
                  {/* Default option */}
                  <button
                    type="button"
                    onClick={() => { setSelectedCollection('default'); setCollectionsOpen(false) }}
                    className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left transition-colors
                               hover:bg-zinc-800 ${selectedCollection === 'default' ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                  >
                    <Folder className="h-3.5 w-3.5 text-zinc-500" />
                    <span className="truncate font-medium">default</span>
                    {selectedCollection === 'default' && (
                      <span className="ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/10 text-zinc-300">active</span>
                    )}
                  </button>

                  {/* Divider */}
                  {collections.filter(c => c.id !== 'default').length > 0 && (
                    <div className="h-px bg-zinc-800" />
                  )}

                  {/* Backend collections */}
                  {collections.filter(c => c.id !== 'default').map((col) => (
                    <button
                      key={col.id}
                      type="button"
                      onClick={() => { setSelectedCollection(col.id); setCollectionsOpen(false) }}
                      className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left transition-colors
                                 hover:bg-zinc-800 ${selectedCollection === col.id ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                    >
                      <Folder className="h-3.5 w-3.5 text-zinc-500" />
                      <span className="flex-1 truncate">{col.name}</span>
                      <span className="text-xs text-zinc-600">{col.total_documents || 0} files</span>
                      {selectedCollection === col.id && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/10 text-zinc-300">active</span>
                      )}
                    </button>
                  ))}

                  {collections.filter(c => c.id !== 'default').length === 0 && !collectionsLoading && (
                    <p className="px-3 py-2.5 text-xs text-zinc-600">No collections yet</p>
                  )}
                </motion.div>
              </>
            )}
          </div>
        </div>

        {/* ─── Error ───────────────────────────────────────────── */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              className="flex items-start gap-3 rounded-lg border border-red-500/25
                         bg-red-500/10 px-4 py-3 text-sm text-red-400"
            >
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Chat history ─────────────────────────────────────── */}
        {history.length > 0 && (
          <div className="flex flex-col gap-5">
            {history.map((turn, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="flex flex-col gap-3"
              >
                {/* question bubble */}
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-white/10 px-5 py-3.5">
                    <p className="text-sm text-zinc-100 leading-relaxed">{turn.question}</p>
                  </div>
                </div>

                {/* answer card */}
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 flex-shrink-0 mt-1">
                    <Sparkles className="h-4 w-4 text-zinc-300" />
                  </div>
                  <div className="flex-1 space-y-3">
                    <p className="text-zinc-200 leading-relaxed">{turn.answer}</p>

                    {/* meta */}
                    <div className="flex items-center gap-4 text-xs text-zinc-500">
                      <span className="inline-flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        {turn.response_time?.toFixed?.(2) ?? '—'}s
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5" />
                        {chunkCount(turn)} chunks
                      </span>
                    </div>

                    {/* citations */}
                    {turn.sources?.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Sources</p>
                        {turn.sources.map((chunk, j) => (
                          <SourceCard key={`${i}-${chunk.chunk_id ?? j}`} chunk={chunk} indexPrefix={`${i}`} />
                        ))}
                      </div>
                    )}

                    <RetrievalDebug items={turn.retrieval_debug} debugKey={`history-${i}`} />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* ─── Empty state ──────────────────────────────────────── */}
        {history.length === 0 && !loading && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center py-16 gap-4"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5">
              <MessageSquare className="h-7 w-7 text-zinc-500" />
            </div>
            <p className="text-zinc-400 text-sm text-center leading-relaxed max-w-md">
              Ask questions about your uploaded documents.
              <br />I'll retrieve relevant passages and synthesize an answer.
            </p>
          </motion.div>
        )}

        {/* ─── Answer card (current, non-history path) ──────────── */}
        {answer && history.length === 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-4"
          >
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 space-y-4">
              <p className="text-zinc-200 text-base leading-relaxed">{answer.answer}</p>
              <div className="flex items-center gap-4 text-xs text-zinc-500">
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {answer.response_time?.toFixed?.(2) ?? '—'}s
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" />
                  {chunkCount(answer)} chunks retrieved
                </span>
              </div>
            </div>

            {/* citations */}
            {answer.sources?.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider pl-1">Retrieved Sources</p>
                {answer.sources.map((chunk, j) => (
                  <SourceCard key={`current-${chunk.chunk_id ?? j}`} chunk={chunk} indexPrefix="current" />
                ))}
              </div>
            )}

            <RetrievalDebug items={answer.retrieval_debug} debugKey="current" />
          </motion.div>
        )}

        {/* ─── Loading ──────────────────────────────────────────── */}
        <AnimatePresence>
          {(loading || sessionLoading) && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center gap-3 py-4"
            >
              <Loader2 className="h-5 w-5 text-zinc-400 animate-spin" />
              <span className="text-zinc-500 text-sm">
                {loading ? 'Thinking…' : 'Loading conversation…'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Resumed-session label ─────────────────────────────── */}
        {urlSessionId && !sessionLoading && history.length > 0 && (
          <p className="text-xs text-zinc-600 flex items-center gap-1.5 -mt-2">
            <Clock className="h-3.5 w-3.5" />
            Resumed chat session
          </p>
        )}

        {/* ─── Input bar ────────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
          className="sticky bottom-4 pt-2"
        >
          <form onSubmit={handleSend}
            className="flex items-end gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/80
                       p-2 pl-4 shadow-2xl shadow-black/40 backdrop-blur-xl"
          >
            <textarea
              ref={inputRef}
              rows={1}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents…"
              disabled={loading}
              className="flex-1 bg-transparent text-sm text-white
                         placeholder-zinc-600 outline-none resize-none
                         max-h-40 py-2.5 leading-relaxed"
            />
            <button
              type="submit"
              disabled={!question.trim() || loading}
              className="h-10 px-5 rounded-xl bg-white text-black text-sm font-medium
                         hover:bg-zinc-200 disabled:opacity-35 disabled:cursor-not-allowed
                         transition-all active:scale-[0.97] flex items-center gap-2"
            >
              {loading ? (
                <> <Loader2 className="h-4 w-4 animate-spin" /> Sending </>
              ) : (
                <> <Send className="h-4 w-4" /> Ask </>
              )}
            </button>
          </form>
        </motion.div>

      </div>
    </div>
  )
}
