import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  MessageSquare,
  Clock,
  FileText,
  Hash,
  AlertCircle,
  Loader2,
  Search,
  Trash2,
  MessageCircle,
} from 'lucide-react'

import { useAuth } from '../contexts/AuthContext'
import {
  fetchChatSession,
  fetchChatSessions,
  deleteChatSession,
} from '../services/api'
import { useApp } from '../AppContext'
import { useNavigate } from 'react-router-dom'

const relevanceColor = (score) => {
  const pct = (score ?? 0) * 100

  if (pct >= 80) return 'bg-emerald-500'
  if (pct >= 55) return 'bg-amber-500'

  return 'bg-red-500'
}

const asArray = (value) => (Array.isArray(value) ? value : [])

const parseSources = (raw) => {
  if (!raw) return []
  if (typeof raw === 'object') return raw // Handles both arrays and objects natively
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
}

const chunkCount = (turn) =>
  turn?.retrieved_chunks ?? turn?.retrieval_count ?? turn?.sources?.length ?? 0

export default function History() {
  const { chatHistory } = useApp()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [expandedIdx, setExpandedIdx] = useState(null)
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingSession, setDeletingSession] = useState(null)
  const [toast, setToast] = useState(null)

  async function loadSessions() {
    if (!user?.id) {
      setSessions([])
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const r = await fetchChatSessions(user.id)

      console.log('Sessions response:', r)

      const sessionSummaries = asArray(r.data)
      const sessionsWithMessages = await Promise.all(
        sessionSummaries.map(async (session) => {
          try {
            const detail = await fetchChatSession(session.id, user.id)
            return {
              ...session,
              messages: asArray(detail.data?.messages),
            }
          } catch (err) {
            console.error('Failed to load session messages', err)
            return {
              ...session,
              messages: [],
            }
          }
        })
      )

      setSessions(sessionsWithMessages)
    } catch (err) {
      console.error(err)
      setError('Failed to load chat history')
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    loadSessions()
  }, [user?.id])

  useEffect(() => {
    const onFocus = () => {
      loadSessions()
    }

    window.addEventListener('focus', onFocus)

    return () => window.removeEventListener('focus', onFocus)
  }, [user?.id])
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  // Flatten sessions + messages
  const sessionList = asArray(sessions)
  const localHistory = asArray(chatHistory)
  const hasSessions = sessionList.length > 0

  const historyItems = hasSessions
    ? sessionList.flatMap((session) =>
        (session.messages || []).map((msg) => {
          const rawSources = parseSources(msg.sources ?? msg.sources_json)
          let sourcesArray = rawSources
          let parsedChunks = msg.retrieved_chunks

          // Fallback if sources was saved as an object containing retrieved_chunks
          if (rawSources && !Array.isArray(rawSources) && typeof rawSources === 'object') {
            sourcesArray = rawSources.sources || []
            if (rawSources.retrieved_chunks !== undefined) {
              parsedChunks = rawSources.retrieved_chunks
            } else if (rawSources.retrieval_count !== undefined) {
              parsedChunks = rawSources.retrieval_count
            }
          }

          return {
            ...msg,
            sources: sourcesArray,
            retrieved_chunks: parsedChunks,
            retrieval_count: msg.retrieval_count,
            session_title: session.title,
            session_id: session.id,
          }
        })
      )
    : localHistory

  const validHistoryItems = historyItems

  const filteredHistory = searchQuery.trim()
    ? validHistoryItems.filter(
        (item) =>
          item.question
            ?.toLowerCase()
            .includes(searchQuery.toLowerCase()) ||
          item.answer
            ?.toLowerCase()
            .includes(searchQuery.toLowerCase())
      )
    : validHistoryItems

  const handleDeleteSession = async (sessionId, title) => {
    const ok = confirm(
      `Delete session "${title}"?\n\nThis cannot be undone.`
    )

    if (!ok) return

    setDeletingSession(sessionId)

    try {
      await deleteChatSession(sessionId, user?.id)

      // normalized schema
      setSessions((prev) =>
        asArray(prev).filter((s) => s.id !== sessionId)
      )

      setToast({
        type: 'success',
        message: 'Session deleted',
      })
    } catch (err) {
      console.error(err)

      setToast({
        type: 'error',
        message: 'Failed to delete session',
      })
    } finally {
      setDeletingSession(null)
    }

    setTimeout(() => setToast(null), 3000)
  }

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50">
          <div
            className={`rounded-lg px-4 py-3 text-sm border ${
              toast.type === 'success'
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
                : 'bg-red-500/15 text-red-400 border-red-500/20'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Chat History
            </h1>

            <p className="text-zinc-400 text-sm mt-1">
              Previous Q&A sessions
            </p>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />

            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 h-9 rounded-lg border border-zinc-800 bg-zinc-900/80 pl-9 pr-3 text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Content */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
            </div>
          ) : filteredHistory.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center gap-3 py-12 text-zinc-500"
            >
              <MessageSquare className="h-8 w-8" />

              <p className="text-sm">
                {searchQuery
                  ? 'No results found'
                  : 'No chat history yet. Switch to Chat to start.'}
              </p>
            </motion.div>
          ) : (
            filteredHistory.map((turn, i) => (
              <motion.div
                key={`${turn.session_id || 'local'}-${i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 overflow-hidden"
              >
                {/* Header */}
                <div
                  className="flex items-center justify-between p-4 cursor-pointer"
                  onClick={(e) => {
                    if (!e.target.closest('button')) {
                      setExpandedIdx(
                        expandedIdx === i ? null : i
                      )
                    }
                  }}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 flex-shrink-0">
                      <span className="text-xs font-semibold text-zinc-300">
                        Q{i + 1}
                      </span>
                    </span>

                    <span className="flex-1 text-sm text-zinc-300 truncate">
                      {turn.question}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <span className="text-xs text-zinc-500 flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {turn.response_time?.toFixed?.(1) ?? '—'}s
                    </span>

                    <span className="text-xs text-zinc-500">
                      {chunkCount(turn)} chunks
                    </span>

                    {turn.session_id && turn.session_id !== 'default' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()

                          handleDeleteSession(
                            turn.session_id,
                            turn.session_title
                          )
                        }}
                        disabled={
                          deletingSession === turn.session_id
                        }
                        className="p-1.5 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded */}
                {expandedIdx === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{
                      height: 'auto',
                      opacity: 1,
                    }}
                    exit={{
                      height: 0,
                      opacity: 0,
                    }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden border-t border-zinc-800/60"
                  >
                    <div className="px-5 py-4 space-y-3">
                      {/* Answer */}
                      <div>
                        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-1.5">
                          Answer
                        </p>

                        <p className="text-zinc-200 text-sm leading-relaxed">
                          {turn.answer}
                        </p>
                      </div>

                      {/* Meta */}
                      <div className="flex items-center gap-4 text-xs text-zinc-500">
                        <span className="inline-flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          {turn.response_time?.toFixed?.(2) ??
                            '—'}
                          s
                        </span>

                        <span className="inline-flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5" />
                          {chunkCount(turn)} chunks
                        </span>
                      </div>

                      {/* Sources */}
                      {turn.sources?.length > 0 && (
                        <div className="space-y-2 pt-1">
                          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                            Sources
                          </p>

                          {turn.sources.map((src, j) => (
                            <div
                              key={j}
                              className="rounded-lg border border-zinc-800/80 bg-zinc-800/40 px-4 py-2.5 flex items-center gap-3"
                            >
                              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-700 flex-shrink-0">
                                <FileText className="h-3.5 w-3.5 text-zinc-400" />
                              </div>

                              <span className="flex-1 text-sm text-zinc-300 truncate">
                                {src.source_file}
                              </span>

                              <span className="text-xs text-zinc-500 flex items-center gap-1">
                                <Hash className="h-3 w-3" />
                                p.{src.page_number}
                              </span>

                              <span
                                className={`text-xs font-medium px-2 py-0.5 rounded-full ${relevanceColor(
                                  src.relevance_score
                                )} text-white/90`}
                              >
                                {Math.round(
                                  (src.relevance_score ?? 0) * 100
                                )}
                                %
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Resume Button */}
                      {turn.session_id && turn.session_id !== 'default' && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()

                            navigate(
                              `/chat/${turn.session_id}`
                            )
                          }}
                          className="mt-2 inline-flex items-center gap-2 rounded-xl bg-white/10 hover:bg-white/15 text-white text-sm font-medium px-4 py-2.5 transition-colors"
                        >
                          <MessageCircle className="h-4 w-4" />
                          Resume Chat
                        </button>
                      )}
                    </div>
                  </motion.div>
                )}
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
