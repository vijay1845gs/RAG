import { useState, useEffect, useMemo, useRef } from 'react'
import {
  FileText,
  CheckCircle,
  Clock,
  Trash2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Folder,
  ChevronDown,
  Search,
  Eye,
  Edit2,
  MoreVertical,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  RotateCcw,
  XCircle,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  fetchDocuments,
  deleteDocument,
  fetchCollections,
  retryDocumentProcessing,
} from '../services/api'
import { useApp } from '../AppContext'
import { useAuth } from '../contexts/AuthContext'

// 5-state status badge system
const STATUS_CONFIG = {
  completed: {
    classes: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/20',
    dot: '●',
    pulse: false,
  },
  processing: {
    classes: 'text-blue-400 bg-blue-500/15 border-blue-500/20',
    dot: '●',
    pulse: true,
  },
  queued: {
    classes: 'text-amber-400 bg-amber-500/15 border-amber-500/20',
    dot: '●',
    pulse: true,
  },
  retrying: {
    classes: 'text-orange-400 bg-orange-500/15 border-orange-500/20',
    dot: '↺',
    pulse: true,
  },
  failed: {
    classes: 'text-red-400 bg-red-500/15 border-red-500/20',
    dot: '✕',
    pulse: false,
  },
}

const statusBadge = (status) => {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.failed
  return cfg.classes
}

function formatDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFileSize(bytes) {
  if (!bytes) return '—'
  const kb = bytes / 1024
  if (kb < 1024) return `${Math.round(kb)} KB`
  const mb = kb / 1024
  return `${Math.round(mb * 10) / 10} MB`
}

export default function Documents() {
  const { uploads, removeUpload } = useApp()
  const { user } = useAuth()

  // Core state
  const [docs, setDocs] = useState([])
  const [collections, setCollections] = useState([])

  // UI state
  const [loading, setLoading] = useState(true)
  const [collectionsLoading, setCollectionsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)

  // Filter & search state
  const [selectedCollectionFilter, setSelectedCollectionFilter] = useState('')
  const [collectionFilterOpen, setCollectionFilterOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Sort state
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState('desc')

  // Pagination state
  const [limit, setLimit] = useState(20)
  const [offset, setOffset] = useState(0)
  const [totalCount, setTotalCount] = useState(0)

  // Modal state
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [previewDoc, setPreviewDoc] = useState(null)
  const [renameDoc, setRenameDoc] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [moveDoc, setMoveDoc] = useState(null)
  const [moveTarget, setMoveTarget] = useState('')

  // Action menu state
  const [openMenuId, setOpenMenuId] = useState(null)

  // Auto-refresh tracking for in-progress documents
  const [autoRefreshCount, setAutoRefreshCount] = useState(0)
  const autoRefreshRef = useRef(null)

  // Load documents on mount and when filters change
  useEffect(() => {
    loadDocuments()
  }, [user?.id, selectedCollectionFilter, searchQuery, sortBy, sortOrder, limit, offset])

  // Load collections on mount
  useEffect(() => {
    if (!user?.id) return
    setCollectionsLoading(true)
    fetchCollections(user.id)
      .then((r) => setCollections(Array.isArray(r.data) ? r.data : []))
      .catch(() => setCollections([]))
      .finally(() => setCollectionsLoading(false))
  }, [user?.id])

  const loadDocuments = async () => {
    if (!user?.id) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.append('user_id', user.id)
      if (selectedCollectionFilter) params.append('collection_id', selectedCollectionFilter)
      if (searchQuery) params.append('search', searchQuery)
      params.append('sort_by', sortBy)
      params.append('sort_order', sortOrder)
      params.append('limit', limit.toString())
      params.append('offset', offset.toString())

      const response = await fetch(
        `http://localhost:8000/api/v1/documents?${params.toString()}`
      )
      const data = await response.json()

      if (data.items) {
        setDocs(data.items)
        setTotalCount(data.total || 0)
      } else {
        setDocs([])
      }
    } catch (err) {
      setError('Failed to load documents')
      setDocs([])
    } finally {
      setLoading(false)
    }
  }

  const collectionNameMap = useMemo(() => {
    const m = new Map()
    collections.forEach((c) => m.set(c.id, c.name))
    return m
  }, [collections])

  const displayedDocs = docs.length > 0 ? docs : uploads

  // Auto-refresh every 5s when any document is queued/processing/retrying
  useEffect(() => {
    const hasInProgress = displayedDocs.some(d => {
      const s = d.processing_status || d.upload_status || ''
      return ['queued', 'processing', 'retrying'].includes(s)
    })

    if (hasInProgress) {
      autoRefreshRef.current = setInterval(() => {
        setAutoRefreshCount(c => c + 1)
        loadDocuments()
      }, 5000)
    } else {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current)
    }

    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current)
    }
  }, [displayedDocs])

  // Handlers
  const handleSort = (newSortBy) => {
    if (sortBy === newSortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(newSortBy)
      setSortOrder('desc')
    }
    setOffset(0)
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    const { id } = deleteConfirm
    try {
      await deleteDocument(id, user?.id)
      setDocs((prev) => prev.filter((d) => d.document_id !== id))
      removeUpload(id)
      showToast('Document deleted successfully', 'success')
      loadDocuments()
    } catch (err) {
      const status = err?.response?.status
      if (status === 404) {
        // Document not in DB — remove from local state only
        setDocs((prev) => prev.filter((d) => d.document_id !== id))
        removeUpload(id)
        showToast('Document removed', 'success')
        loadDocuments()
      } else {
        showToast('Failed to delete document', 'error')
      }
    } finally {
      setDeleteConfirm(null)
      setOpenMenuId(null)
    }
  }

  const handleRename = async () => {
    if (!renameDoc || !renameValue.trim()) return
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/${renameDoc.document_id}?user_id=${user?.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: renameValue }),
        }
      )
      if (response.ok) {
        setDocs((prev) =>
          prev.map((d) =>
            d.document_id === renameDoc.document_id
              ? { ...d, filename: renameValue }
              : d
          )
        )
        showToast('Document renamed successfully', 'success')
        setRenameDoc(null)
        setRenameValue('')
        setOpenMenuId(null)
      }
    } catch (err) {
      showToast('Failed to rename document', 'error')
    }
  }

  const handleMove = async () => {
    if (!moveDoc || !moveTarget) return
    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/documents/${moveDoc.document_id}/collection?user_id=${user?.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ collection_id: moveTarget }),
        }
      )
      if (response.ok) {
        setDocs((prev) =>
          prev.map((d) =>
            d.document_id === moveDoc.document_id
              ? { ...d, collection_id: moveTarget }
              : d
          )
        )
        showToast('Document moved successfully', 'success')
        setMoveDoc(null)
        setMoveTarget('')
        setOpenMenuId(null)
      }
    } catch (err) {
      showToast('Failed to move document', 'error')
    }
  }

  const showToast = (message, type) => {
    setToast({ type, message })
    setTimeout(() => setToast(null), 3000)
  }

  const handleRetry = async (doc) => {
    setOpenMenuId(null)
    try {
      await retryDocumentProcessing(doc.document_id, user?.id)
      setDocs(prev => prev.map(d =>
        d.document_id === doc.document_id
          ? { ...d, processing_status: 'queued', processing_progress: 0, processing_error: null }
          : d
      ))
      showToast('Document re-queued for processing', 'success')
    } catch (err) {
      showToast(err?.response?.data?.detail || 'Failed to retry document', 'error')
    }
  }

  const totalPages = Math.ceil(totalCount / limit)
  const currentPage = Math.floor(offset / limit) + 1
  const canPrevious = offset > 0
  const canNext = currentPage < totalPages

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-4 right-4 z-50"
          >
            <div
              className={`rounded-lg px-4 py-3 text-sm ${
                toast.type === 'success'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                  : 'bg-red-500/15 text-red-400 border border-red-500/20'
              }`}
            >
              {toast.message}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col gap-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-zinc-400 text-sm mt-1">
            {loading ? 'Loading…' : `${totalCount} document${totalCount !== 1 ? 's' : ''}`}
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-col gap-4">
          {/* Row 1: Search + Collection Filter + Refresh */}
          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500 pointer-events-none" />
              <input
                type="text"
                placeholder="Search documents…"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setOffset(0)
                }}
                className="w-full h-9 pl-9 pr-3 rounded-lg border border-zinc-800 bg-zinc-900/80
                           text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
              />
            </div>

            {/* Collection Filter */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setCollectionFilterOpen(!collectionFilterOpen)}
                className="flex items-center gap-2 h-9 rounded-lg border border-zinc-800 bg-zinc-900/80
                           px-3 text-sm text-zinc-300 hover:bg-zinc-800 transition-colors min-w-[180px]"
              >
                <Folder className="h-4 w-4" />
                <span className="flex-1 text-left truncate">
                  {collectionsLoading
                    ? 'Loading…'
                    : selectedCollectionFilter
                    ? collections.find((c) => c.id === selectedCollectionFilter)?.name || 'Unknown'
                    : 'All collections'}
                </span>
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${collectionFilterOpen ? 'rotate-180' : ''}`} />
              </button>

              {collectionFilterOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setCollectionFilterOpen(false)} />
                  <div className="absolute z-50 top-full right-0 mt-1.5 w-52 rounded-xl border border-zinc-800 bg-zinc-900 shadow-xl shadow-black/40 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedCollectionFilter('')
                        setCollectionFilterOpen(false)
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm transition-colors hover:bg-zinc-800
                                 ${!selectedCollectionFilter ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                    >
                      <Folder className="h-3.5 w-3.5" />
                      <span>All collections</span>
                    </button>
                    <div className="h-px bg-zinc-800" />
                    {collections.map((col) => (
                      <button
                        key={col.id}
                        type="button"
                        onClick={() => {
                          setSelectedCollectionFilter(col.id)
                          setCollectionFilterOpen(false)
                        }}
                        className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm transition-colors hover:bg-zinc-800
                                   ${selectedCollectionFilter === col.id ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                      >
                        <Folder className="h-3.5 w-3.5" />
                        <span className="truncate">{col.name}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Refresh */}
            <button
              onClick={loadDocuments}
              disabled={loading}
              className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors disabled:opacity-50"
              title="Refresh documents"
            >
              <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Row 2: Limit selector + Pagination info */}
          <div className="flex items-center justify-between text-sm text-zinc-400">
            <div className="flex items-center gap-2">
              <label htmlFor="limit" className="text-xs">
                Show:
              </label>
              <select
                id="limit"
                value={limit}
                onChange={(e) => {
                  setLimit(parseInt(e.target.value, 10))
                  setOffset(0)
                }}
                className="h-8 px-2 rounded-lg border border-zinc-800 bg-zinc-900 text-white text-xs focus:outline-none focus:border-zinc-700"
              >
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </div>

            <div>
              {totalCount > 0 ? (
                <span>
                  Page {currentPage} of {totalPages} ({totalCount} total)
                </span>
              ) : (
                <span>No documents</span>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-zinc-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-xs text-zinc-500 uppercase tracking-wider bg-zinc-900/50">
                <th className="px-5 py-3 text-left">
                  <button
                    onClick={() => handleSort('filename')}
                    className="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                  >
                    Filename
                    <ArrowUpDown className={`h-3 w-3 ${sortBy === 'filename' ? 'text-white' : 'opacity-0'}`} />
                  </button>
                </th>
                <th className="px-5 py-3 text-left">
                  <button
                    onClick={() => handleSort('collection_id')}
                    className="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                  >
                    Collection
                    <ArrowUpDown className={`h-3 w-3 ${sortBy === 'collection_id' ? 'text-white' : 'opacity-0'}`} />
                  </button>
                </th>
                <th className="px-5 py-3 text-left">
                  <button
                    onClick={() => handleSort('created_at')}
                    className="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                  >
                    Uploaded
                    <ArrowUpDown className={`h-3 w-3 ${sortBy === 'created_at' ? 'text-white' : 'opacity-0'}`} />
                  </button>
                </th>
                <th className="px-5 py-3 text-left">Pages</th>
                <th className="px-5 py-3 text-left">
                  <button
                    onClick={() => handleSort('total_chunks')}
                    className="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                  >
                    Chunks
                    <ArrowUpDown className={`h-3 w-3 ${sortBy === 'total_chunks' ? 'text-white' : 'opacity-0'}`} />
                  </button>
                </th>
                <th className="px-5 py-3 text-left">
                  <button
                    onClick={() => handleSort('upload_status')}
                    className="flex items-center gap-1 hover:text-zinc-400 transition-colors"
                  >
                    Status
                    <ArrowUpDown className={`h-3 w-3 ${sortBy === 'upload_status' ? 'text-white' : 'opacity-0'}`} />
                  </button>
                </th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10">
                    <div className="flex items-center justify-center gap-2 text-zinc-500">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Loading documents…
                    </div>
                  </td>
                </tr>
              ) : displayedDocs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-zinc-500">
                    {searchQuery || selectedCollectionFilter ? 'No documents match your search.' : 'No documents uploaded yet.'}
                  </td>
                </tr>
              ) : (
                displayedDocs.map((doc) => (
                  <tr key={doc.document_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <FileText className="h-4 w-4 text-zinc-400 flex-shrink-0" />
                        <div className="flex flex-col min-w-0">
                          <span className="font-medium text-white truncate max-w-xs">{doc.filename}</span>
                          <span className="font-mono text-[10px] text-zinc-600 truncate">{doc.document_id}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium bg-zinc-800/60 border-zinc-700 text-zinc-300">
                        <Folder className="h-3 w-3" />
                        {collectionNameMap.get(doc.collection_id) || 'default'}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-zinc-400 whitespace-nowrap">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-5 py-3 text-zinc-300">{doc.total_pages ?? '—'}</td>
                    <td className="px-5 py-3 text-zinc-300">{doc.total_chunks ?? '—'}</td>
                    <td className="px-5 py-3">
                      {(() => {
                        const effectiveStatus = doc.processing_status || doc.upload_status || 'unknown'
                        const cfg = STATUS_CONFIG[effectiveStatus] || STATUS_CONFIG.failed
                        const progress = doc.processing_progress || 0
                        const isBusy = ['queued', 'processing', 'retrying'].includes(effectiveStatus)
                        return (
                          <div className="space-y-1.5">
                            <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.classes}`}>
                              <span className={cfg.pulse ? 'animate-pulse' : ''}>{cfg.dot}</span>
                              {effectiveStatus}
                            </div>
                            {isBusy && progress > 0 && (
                              <div className="w-20 h-1 rounded-full bg-zinc-800 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-current transition-all duration-500"
                                  style={{ width: `${progress}%` }}
                                />
                              </div>
                            )}
                            {effectiveStatus === 'failed' && (
                              <button
                                onClick={() => handleRetry(doc)}
                                className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
                              >
                                <RotateCcw className="h-3 w-3" />
                                Retry
                              </button>
                            )}
                          </div>
                        )
                      })()}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="relative inline-block">
                        <button
                          onClick={() => setOpenMenuId(openMenuId === doc.document_id ? null : doc.document_id)}
                          className="p-2 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>

                        {openMenuId === doc.document_id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
                            <div className="absolute z-50 right-0 mt-1 w-48 rounded-lg border border-zinc-800 bg-zinc-900 shadow-xl shadow-black/40 overflow-hidden">
                              <button
                                onClick={() => setPreviewDoc(doc)}
                                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                              >
                                <Eye className="h-4 w-4" />
                                Preview
                              </button>
                              <button
                                onClick={() => {
                                  setRenameDoc(doc)
                                  setRenameValue(doc.filename)
                                  setOpenMenuId(null)
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                              >
                                <Edit2 className="h-4 w-4" />
                                Rename
                              </button>
                              <button
                                onClick={() => {
                                  setMoveDoc(doc)
                                  setMoveTarget(doc.collection_id)
                                  setOpenMenuId(null)
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                              >
                                <Folder className="h-4 w-4" />
                                Move Collection
                              </button>
                              <div className="h-px bg-zinc-800" />
                              {/* Retry option for failed documents */}
                              {(['failed'].includes(doc.processing_status || doc.upload_status)) && (
                                <>
                                  <button
                                    onClick={() => handleRetry(doc)}
                                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-orange-400 hover:bg-orange-500/10 transition-colors"
                                  >
                                    <RotateCcw className="h-4 w-4" />
                                    Retry Processing
                                  </button>
                                  <div className="h-px bg-zinc-800" />
                                </>
                              )}
                              <button
                                onClick={() => {
                                  setDeleteConfirm({ id: doc.document_id, filename: doc.filename })
                                  setOpenMenuId(null)
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                              >
                                <Trash2 className="h-4 w-4" />
                                Delete
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalCount > limit && (
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={!canPrevious || loading}
              className="p-2 rounded-lg border border-zinc-800 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = i + 1
              if (totalPages > 5 && pageNum > 3 && pageNum < totalPages - 1) return null
              if (totalPages > 5 && pageNum === 3 && currentPage > 5) return <span key="ellipsis">…</span>

              return (
                <button
                  key={pageNum}
                  onClick={() => setOffset((pageNum - 1) * limit)}
                  className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                    currentPage === pageNum
                      ? 'bg-white text-black font-semibold'
                      : 'border border-zinc-800 text-zinc-300 hover:bg-zinc-800'
                  }`}
                >
                  {pageNum}
                </button>
              )
            })}

            <button
              onClick={() => setOffset(offset + limit)}
              disabled={!canNext || loading}
              className="p-2 rounded-lg border border-zinc-800 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 max-w-sm w-full mx-4"
            >
              <h3 className="text-lg font-semibold mb-2">Delete Document?</h3>
              <p className="text-zinc-400 text-sm mb-6">
                Are you sure you want to delete <strong>"{deleteConfirm.filename}"</strong>? This action cannot be undone and will remove all associated chunks from the vector store.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 px-4 py-2 rounded-lg border border-zinc-800 text-white hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  className="flex-1 px-4 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors font-medium"
                >
                  Delete
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Preview Modal */}
      <AnimatePresence>
        {previewDoc && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto"
            >
              <h3 className="text-lg font-semibold mb-4">Document Preview</h3>

              <div className="space-y-3 text-sm">
                <div>
                  <label className="text-xs text-zinc-500 uppercase">Filename</label>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="font-mono text-white">{previewDoc.filename}</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(previewDoc.filename)
                        showToast('Copied to clipboard', 'success')
                      }}
                      className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                <div>
                  <label className="text-xs text-zinc-500 uppercase">Document ID</label>
                  <span className="font-mono text-xs text-zinc-400 mt-1 block truncate">{previewDoc.document_id}</span>
                </div>

                <div className="pt-2">
                  <label className="text-xs text-zinc-500 uppercase">Collection</label>
                  <span className="text-white mt-1 block">{collectionNameMap.get(previewDoc.collection_id) || 'Unknown'}</span>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2">
                  <div>
                    <label className="text-xs text-zinc-500 uppercase">Pages</label>
                    <span className="text-white font-semibold mt-1 block">{previewDoc.total_pages ?? '—'}</span>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 uppercase">Chunks</label>
                    <span className="text-white font-semibold mt-1 block">{previewDoc.total_chunks ?? '—'}</span>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500 uppercase">Size</label>
                    <span className="text-white font-semibold mt-1 block">{formatFileSize(previewDoc.file_size)}</span>
                  </div>
                </div>

                <div className="pt-2">
                  <label className="text-xs text-zinc-500 uppercase">Uploaded</label>
                  <span className="text-white mt-1 block">{formatDate(previewDoc.created_at)}</span>
                </div>

                <div className="pt-2">
                  <label className="text-xs text-zinc-500 uppercase">Status</label>
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium mt-1 ${statusBadge(previewDoc.upload_status)}`}>
                    {previewDoc.upload_status || '—'}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setPreviewDoc(null)}
                className="w-full mt-6 px-4 py-2 rounded-lg border border-zinc-800 text-white hover:bg-zinc-800 transition-colors"
              >
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rename Modal */}
      <AnimatePresence>
        {renameDoc && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 max-w-sm w-full mx-4"
            >
              <h3 className="text-lg font-semibold mb-4">Rename Document</h3>
              <input
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                placeholder="New filename"
                className="w-full px-3 py-2 rounded-lg border border-zinc-800 bg-zinc-800 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700 mb-4"
              />
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setRenameDoc(null)
                    setRenameValue('')
                  }}
                  className="flex-1 px-4 py-2 rounded-lg border border-zinc-800 text-white hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRename}
                  disabled={!renameValue.trim()}
                  className="flex-1 px-4 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors font-medium disabled:opacity-50"
                >
                  Rename
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Move Collection Modal */}
      <AnimatePresence>
        {moveDoc && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 max-w-sm w-full mx-4"
            >
              <h3 className="text-lg font-semibold mb-4">Move to Collection</h3>
              <select
                value={moveTarget}
                onChange={(e) => setMoveTarget(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-zinc-800 bg-zinc-800 text-white focus:outline-none focus:border-zinc-700 mb-4"
              >
                <option value="">Select a collection…</option>
                {collections.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.name}
                  </option>
                ))}
              </select>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    setMoveDoc(null)
                    setMoveTarget('')
                  }}
                  className="flex-1 px-4 py-2 rounded-lg border border-zinc-800 text-white hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleMove}
                  disabled={!moveTarget}
                  className="flex-1 px-4 py-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors font-medium disabled:opacity-50"
                >
                  Move
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
