import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  FileText,
  MessageSquare,
  Upload,
  Zap,
  CheckCircle,
  XCircle,
  Folder,
  Cpu,
  Database,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import {
  checkHealth,
  fetchDocuments,
  fetchChatSession,
  fetchChatSessions,
  fetchCollections,
  fetchQueueStats,
} from '../services/api'
import { useApp } from '../AppContext'
import { useAuth } from '../contexts/AuthContext'

const statCards = [
  { icon: FileText, label: 'Documents', key: 'documents', color: 'text-blue-400 bg-blue-400/15' },
  { icon: MessageSquare, label: 'Chat Turns', key: 'chats', color: 'text-emerald-400 bg-emerald-400/15' },
  { icon: Upload, label: 'Uploads', key: 'uploads', color: 'text-amber-400 bg-amber-400/15' },
  { icon: Folder, label: 'Collections', key: 'collections', color: 'text-purple-400 bg-purple-400/15' },
]

function formatDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const asArray = (value) => (Array.isArray(value) ? value : [])

export default function Dashboard() {
  const { uploads, chatHistory } = useApp()
  const { user } = useAuth()
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [stats, setStats] = useState({
    documents: '—',
    chats: '—',
    uploads: '—',
    collections: '—',
    docsPerCollection: {},
    collectionsById: {},
    latestCollection: null,
  })
  const [queueStats, setQueueStats] = useState(null)
  const [queueLoading, setQueueLoading] = useState(false)

  useEffect(() => {
    checkHealth()
      .then((r) => setHealth(r.data))
      .catch(() => setErr('Backend unreachable'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const loadStats = async () => {
      if (!user?.id) return
      try {
        const [docsRes, sessionsRes, collectionsRes] = await Promise.all([
          fetchDocuments(user.id),
          fetchChatSessions(user.id),
          fetchCollections(user.id),
        ])
        
        // Handle paginated response from fetchDocuments
        let apiDocs = []
        let apiDocumentCount = 0
        if (docsRes.data) {
          // Check if it's a paginated response with items
          if (docsRes.data.items && Array.isArray(docsRes.data.items)) {
            apiDocs = docsRes.data.items
            apiDocumentCount = docsRes.data.total ?? apiDocs.length
          } else if (Array.isArray(docsRes.data)) {
            apiDocs = docsRes.data
            apiDocumentCount = apiDocs.length
          }
        }
        
        const apiSessions  = asArray(sessionsRes.data)
        const apiColls     = asArray(collectionsRes.data)

        const sessionMessages = await Promise.all(
          apiSessions.map(async (session) => {
            try {
              const detail = await fetchChatSession(session.id, user.id)
              return asArray(detail.data?.messages)
            } catch (err) {
              console.error('Failed to load dashboard chat count:', err)
              return []
            }
          })
        )
        const chatTurnCount = sessionMessages.reduce(
          (total, messages) => total + messages.length,
          0
        )

        const docsPerCol = {}
        apiDocs.forEach(d => {
          const c = d.collection_id || 'default'
          docsPerCol[c] = (docsPerCol[c] || 0) + 1
        })
        const collectionsById = Object.fromEntries(
          apiColls.map((collection) => [collection.id, collection])
        )

        const latestColl = apiColls.length > 0
          ? apiColls.reduce((latest, c) => new Date(c.created_at) > new Date(latest.created_at) ? c : latest)
          : null

        setStats({
          documents:    apiDocumentCount || uploads.length || 0,
          chats:        chatTurnCount || chatHistory.length || 0,
          uploads:      uploads.length || 0,
          collections:  apiColls.length || 0,
          docsPerCollection: docsPerCol,
          collectionsById,
          latestCollection:  latestColl,
        })
      } catch (err) {
        console.error('Failed to load dashboard stats:', err)
        setStats(prev => ({
          ...prev,
          documents:    uploads.length || 0,
          chats:        chatHistory.length || 0,
          uploads:      uploads.length || 0,
          collections: 0,
        }))
      }
    }
    loadStats()
  }, [user?.id, uploads, chatHistory])

  // Load queue stats
  useEffect(() => {
    if (!user?.id) return
    setQueueLoading(true)
    fetchQueueStats(user.id)
      .then(r => setQueueStats(r.data))
      .catch(() => setQueueStats(null))
      .finally(() => setQueueLoading(false))
  }, [user?.id])

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-zinc-400 text-sm mt-1">
            {stats.documents !== '—' && stats.documents > 0
              ? `${stats.documents} document${stats.documents !== 1 ? 's' : ''} · ${stats.chats} chat turn${stats.chats !== 1 ? 's' : ''}`
              : 'System overview and quick actions'}
          </p>
        </div>

        {/* Health card */}
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <Activity className="h-5 w-5 text-zinc-400" />
            <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">Backend Status</h2>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 text-zinc-500">
              <div className="h-4 w-4 rounded-full border-2 border-zinc-600 border-t-white animate-spin" />
              Checking…
            </div>
          ) : err ? (
            <div className="flex items-center gap-2 text-red-400">
              <XCircle className="h-5 w-5" />{err}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-emerald-400" />
              <span className="text-white font-medium">Online</span>
              {health && (
                <span className="text-xs text-zinc-500 ml-2">
                  v{health.api_version || '—'} · {health.app_name || 'RAG Backend'}
                </span>
              )}
            </div>
          )}
        </motion.div>

        {/* Stat cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map(({ icon: Icon, label, key, color }) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5"
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <p className="text-2xl font-bold mt-3">{stats[key] ?? '—'}</p>
              <p className="text-xs text-zinc-500 mt-1">{label}</p>
            </motion.div>
          ))}
        </div>

        {/* Documents by Collection */}
        {stats.docsPerCollection && Object.keys(stats.docsPerCollection).length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider mb-3">Documents by Collection</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {Object.entries(stats.docsPerCollection)
                .sort(([, a], [, b]) => b - a)
                .map(([collectionId, count]) => {
                  const collectionName =
                    collectionId === 'default'
                      ? 'default'
                      : stats.collectionsById?.[collectionId]?.name || collectionId

                  return (
                  <div key={collectionId} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                    <div className="flex items-center gap-2.5 mb-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-white/10">
                        <Folder className="h-3.5 w-3.5 text-zinc-300" />
                      </div>
                      <span className="text-sm font-medium text-white truncate">{collectionName}</span>
                    </div>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xl font-bold text-white">{count}</span>
                      <span className="text-xs text-zinc-500">document{count !== 1 ? 's' : ''}</span>
                    </div>
                  </div>
                  )
                })}
            </div>
          </div>
        )}

        {/* Latest Collection */}
        {stats.latestCollection && (
          <div>
            <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider mb-3">Latest Collection</h2>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5 flex items-center gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-400/15 flex-shrink-0">
                <Folder className="h-5 w-5 text-purple-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-white truncate">{stats.latestCollection.name}</p>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Created {formatDate(stats.latestCollection.created_at)}
                  {stats.latestCollection.description ? ` · ${stats.latestCollection.description}` : ''}
                </p>
              </div>
              <span className="text-xs text-zinc-600">
                {stats.docsPerCollection?.[stats.latestCollection.id] ??
                  stats.latestCollection.total_documents ??
                  0}{' '}
                docs
              </span>
            </div>
          </div>
        )}

        {/* Queue Intelligence Widget */}
        {(queueStats || queueLoading) && (
          <div>
            <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Cpu className="h-3.5 w-3.5" />
              Queue Intelligence
            </h2>
            {queueLoading ? (
              <div className="flex items-center gap-2 text-zinc-500 text-sm">
                <RefreshCw className="h-4 w-4 animate-spin" /> Loading queue stats…
              </div>
            ) : queueStats ? (
              <div className="space-y-4">
                {/* Job counts */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: 'Queued',    value: queueStats.queued_jobs,    color: 'text-amber-400 bg-amber-400/10 border-amber-500/20' },
                    { label: 'Active',    value: queueStats.active_jobs,    color: 'text-blue-400 bg-blue-400/10 border-blue-500/20' },
                    { label: 'Failed',    value: queueStats.failed_jobs,    color: 'text-red-400 bg-red-400/10 border-red-500/20' },
                    { label: 'Completed', value: queueStats.completed_jobs,  color: 'text-emerald-400 bg-emerald-400/10 border-emerald-500/20' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className={`rounded-xl border ${color} p-4`}>
                      <p className="text-2xl font-bold">{value ?? 0}</p>
                      <p className="text-xs opacity-70 mt-1">{label}</p>
                    </div>
                  ))}
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Completion Rate</p>
                    <p className="text-xl font-bold">
                      {queueStats.completion_rate != null ? `${queueStats.completion_rate}%` : '—'}
                    </p>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Avg Process Time</p>
                    <p className="text-xl font-bold">
                      {queueStats.avg_processing_time != null
                        ? `${queueStats.avg_processing_time}s`
                        : '—'}
                    </p>
                  </div>
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Cache Hit Rate</p>
                    <p className="text-xl font-bold">
                      {queueStats.cache?.hit_rate != null ? `${queueStats.cache.hit_rate}%` : '—'}
                    </p>
                  </div>
                </div>

                {/* Infrastructure status */}
                <div className="flex flex-wrap gap-3">
                  <div className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
                    queueStats.cache?.connected
                      ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                      : 'border-zinc-700 text-zinc-500'
                  }`}>
                    <Database className="h-3 w-3" />
                    Redis {queueStats.cache?.connected ? 'online' : 'offline'}
                    {queueStats.cache?.used_memory && queueStats.cache.used_memory !== '—' && (
                      <span className="opacity-60 ml-1">· {queueStats.cache.used_memory}</span>
                    )}
                  </div>
                  <div className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
                    queueStats.worker?.online
                      ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                      : 'border-zinc-700 text-zinc-500'
                  }`}>
                    <Cpu className="h-3 w-3" />
                    Worker {queueStats.worker?.online ? 'online' : 'offline'}
                    {queueStats.worker?.active_tasks > 0 && (
                      <span className="opacity-60 ml-1">· {queueStats.worker.active_tasks} active</span>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* Quick actions */}
        <div>
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider mb-3">Quick Actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { to: '/upload', icon: Upload, label: 'Upload Documents', desc: 'Ingest a new PDF' },
              { to: '/chat', icon: MessageSquare, label: 'Start Chat', desc: 'Ask your documents' },
            ].map(({ to, icon: Icon, label, desc }) => (
              <Link key={to} to={to}
                className="flex items-center gap-4 rounded-xl border border-zinc-800 bg-zinc-900/60
                           p-4 hover:bg-zinc-800/60 transition-colors group"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/10 group-hover:bg-white/15 transition-colors">
                  <Icon className="h-5 w-5 text-zinc-300" />
                </div>
                <div>
                  <p className="font-medium text-sm text-white">{label}</p>
                  <p className="text-xs text-zinc-500">{desc}</p>
                </div>
                <Zap className="h-4 w-4 text-zinc-600 ml-auto" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
