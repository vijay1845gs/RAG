import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  FileUp,
  ArrowRight,
  Folder,
  ChevronDown,
  Plus,
  RefreshCw,
  Cpu,
  Database,
  Layers,
  Zap,
} from 'lucide-react'
import { submitUpload, fetchCollections, createCollection, fetchDocumentStatus } from '../services/api'
import { useApp } from '../AppContext'
import { useAuth } from '../contexts/AuthContext'

// ─── Processing stage config ─────────────────────────────────────────────────

const STAGES = [
  { id: 'queued',      label: 'Queued',     icon: Loader2,     range: [0,   9],  color: '#f59e0b' },
  { id: 'parsing',     label: 'Parsing',    icon: FileText,    range: [10, 25],  color: '#3b82f6' },
  { id: 'chunking',    label: 'Chunking',   icon: Layers,      range: [26, 39],  color: '#3b82f6' },
  { id: 'embedding',   label: 'Embedding',  icon: Cpu,         range: [40, 80],  color: '#8b5cf6' },
  { id: 'vectorizing', label: 'Vectorizing',icon: Database,    range: [81, 95],  color: '#06b6d4' },
  { id: 'saving',      label: 'Saving',     icon: Zap,         range: [96, 99],  color: '#06b6d4' },
  { id: 'completed',   label: 'Completed',  icon: CheckCircle, range: [100,100], color: '#10b981' },
]

const TERMINAL_STATUSES = new Set(['completed', 'failed'])

// Adaptive polling intervals per status
const POLL_INTERVALS = {
  queued:     5000,
  processing: 3000,
  retrying:   4000,
}

function getStageConfig(stage, status) {
  if (status === 'completed') return STAGES.find(s => s.id === 'completed')
  if (status === 'failed') return null
  return STAGES.find(s => s.id === stage) || STAGES.find(s => s.id === 'queued')
}

function getStageColor(status, stage) {
  if (status === 'completed') return '#10b981'
  if (status === 'failed') return '#ef4444'
  if (status === 'retrying') return '#f97316'
  const cfg = getStageConfig(stage, status)
  return cfg?.color || '#3b82f6'
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function UploadPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { recordUpload } = useApp()

  // File state
  const [file, setFile] = useState(null)

  // Collections state
  const [collections, setCollections] = useState([])
  const [collectionsLoading, setCollectionsLoading] = useState(false)
  const [collectionsOpen, setCollectionsOpen] = useState(false)
  const [selectedUploadCollection, setSelectedUploadCollection] = useState('')
  const [showNewCollection, setShowNewCollection] = useState(false)
  const [newCollectionName, setNewCollectionName] = useState('')
  const [creatingCollection, setCreatingCollection] = useState(false)

  // Upload state
  const [uploadProgress, setUploadProgress] = useState(0) // file transfer progress (0-100)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  // Async processing state
  const [queued, setQueued] = useState(null)         // { document_id, job_id, filename }
  const [processingStatus, setProcessingStatus] = useState(null)  // full status response
  const [pollInterval, setPollInterval] = useState(null)

  const pollRef = useRef(null)
  const collectionsRef = useRef(null)

  /* ── Restore saved collection on mount ── */
  useEffect(() => {
    const saved = localStorage.getItem('upload_selected_collection')
    if (saved) setSelectedUploadCollection(saved)
  }, [])
  useEffect(() => {
    if (selectedUploadCollection) {
      localStorage.setItem('upload_selected_collection', selectedUploadCollection)
    } else {
      localStorage.removeItem('upload_selected_collection')
    }
  }, [selectedUploadCollection])

  /* ── Lazy-load collections ── */
  useEffect(() => {
    if (!user?.id) return
    setCollectionsLoading(true)
    fetchCollections(user.id)
      .then(r => setCollections(Array.isArray(r.data) ? r.data : []))
      .catch(() => setCollections([]))
      .finally(() => setCollectionsLoading(false))
  }, [user?.id])

  /* ── Close collections dropdown on outside click ── */
  useEffect(() => {
    const onClick = (e) => {
      if (collectionsRef.current && !collectionsRef.current.contains(e.target)) {
        setCollectionsOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  /* ── Adaptive polling ── */
  useEffect(() => {
    if (!queued?.document_id) return

    const startPolling = (status) => {
      if (pollRef.current) clearTimeout(pollRef.current)
      if (TERMINAL_STATUSES.has(status)) return

      const interval = POLL_INTERVALS[status] || 3000
      pollRef.current = setTimeout(async () => {
        try {
          const { data } = await fetchDocumentStatus(queued.document_id, user?.id)
          setProcessingStatus(data)

          if (data.status === 'completed') {
            recordUpload({
              document_id: queued.document_id,
              filename:    queued.filename,
              collection_id: selectedUploadCollection || null,
              upload_status: 'completed',
            })
          }

          if (!TERMINAL_STATUSES.has(data.status)) {
            startPolling(data.status)
          }
        } catch (err) {
          // Retry polling even on network error
          startPolling('processing')
        }
      }, interval)
    }

    // Kick off polling immediately
    startPolling(processingStatus?.status || 'queued')

    return () => {
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [queued?.document_id])

  /* ── Cleanup on unmount ── */
  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [])

  /* ── Drag & Drop ── */
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') {
      setFile(dropped)
      setError(null)
      setUploadProgress(0)
      setQueued(null)
      setProcessingStatus(null)
    } else {
      setError('Only PDF files are allowed')
    }
  }, [])

  /* ── File input ── */
  const handleFileChange = (e) => {
    const selected = e.target.files?.[0]
    if (selected?.type === 'application/pdf') {
      setFile(selected)
      setError(null)
      setUploadProgress(0)
      setQueued(null)
      setProcessingStatus(null)
    } else {
      setError('Only PDF files are allowed')
    }
  }

  /* ── Create new collection inline ── */
  const handleCreateCollection = async () => {
    const name = newCollectionName.trim()
    if (!name || name.length < 2 || !user?.id) return
    setCreatingCollection(true)
    setError(null)
    try {
      const { data } = await createCollection(user.id, name)
      setCollections(prev => [data, ...prev])
      setSelectedUploadCollection(data.id)
      setNewCollectionName('')
      setShowNewCollection(false)
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to create collection')
    } finally {
      setCreatingCollection(false)
    }
  }

  /* ── Submit ── */
  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setQueued(null)
    setProcessingStatus(null)

    const formData = new FormData()
    formData.append('file', file)
    if (selectedUploadCollection) formData.append('collection_id', selectedUploadCollection)
    if (user?.id) formData.append('user_id', user.id)

    try {
      const { data } = await submitUpload(formData, setUploadProgress, user?.id)
      // data = { document_id, job_id, status: "queued", filename, ... }
      setQueued({
        document_id: data.document_id,
        job_id:      data.job_id,
        filename:    data.filename,
      })
      setProcessingStatus({ status: 'queued', progress: 0, stage: 'queued' })
    } catch (err) {
      setError(err?.response?.data?.error || err?.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  // Derived values
  const isCompleted   = processingStatus?.status === 'completed'
  const isFailed      = processingStatus?.status === 'failed'
  const isProcessing  = !!queued && !isCompleted && !isFailed
  const progress      = processingStatus?.progress ?? 0
  const stage         = processingStatus?.stage
  const statusLabel   = processingStatus?.status
  const stageColor    = getStageColor(statusLabel, stage)
  const stageCfg      = getStageConfig(stage, statusLabel)
  const StageIcon     = stageCfg?.icon || Loader2

  /* ══════════════════════════════════════════════
     COMPLETED STATE
  ══════════════════════════════════════════════ */
  if (isCompleted && queued) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8">
            <div className="flex items-center gap-4 mb-8">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 flex-shrink-0">
                <CheckCircle className="h-6 w-6 text-emerald-400" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">Processing complete</h2>
                <p className="text-zinc-400 text-sm">Your document has been ingested and is ready for chat</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-8">
              {[
                ['Filename',    queued.filename],
                ['Document ID', queued.document_id],
                ['Job ID',      queued.job_id],
                ['Status',      'Completed'],
              ].map(([label, value], i) => (
                <div key={i} className="space-y-1">
                  <p className="text-zinc-500 text-xs uppercase tracking-wider">{label}</p>
                  <p className={`font-medium ${['Document ID','Job ID'].includes(label) ? 'font-mono text-xs text-zinc-400' : ''} break-all`}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => navigate('/chat')}
                className="flex-1 h-11 rounded-xl bg-white text-black font-medium
                           hover:bg-zinc-200 transition-colors active:scale-[0.99]
                           flex items-center justify-center gap-2"
              >
                <ArrowRight className="h-4 w-4" />
                Start Chatting
              </button>
              <button
                onClick={() => {
                  setFile(null); setQueued(null); setProcessingStatus(null)
                  setUploadProgress(0); setError(null)
                }}
                className="px-5 h-11 rounded-xl border border-zinc-800 text-zinc-300
                           hover:bg-zinc-800 transition-colors"
              >
                Upload Another
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    )
  }

  /* ══════════════════════════════════════════════
     PROCESSING / QUEUED STATE (after upload)
  ══════════════════════════════════════════════ */
  if (queued && !isCompleted) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 space-y-8">
            {/* Header */}
            <div className="flex items-center gap-4">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full flex-shrink-0"
                style={{ backgroundColor: `${stageColor}20` }}
              >
                {isFailed ? (
                  <AlertCircle className="h-6 w-6 text-red-400" />
                ) : (
                  <StageIcon
                    className="h-6 w-6"
                    style={{ color: stageColor }}
                    style={{ color: stageColor, animation: isProcessing && !isFailed ? undefined : undefined }}
                  />
                )}
              </div>
              <div>
                <h2 className="text-xl font-semibold">
                  {isFailed ? 'Processing Failed' : 'Processing Document'}
                </h2>
                <p className="text-zinc-400 text-sm">{queued.filename}</p>
              </div>
            </div>

            {/* Progress bar */}
            {!isFailed && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400 capitalize">
                    {stage || statusLabel || 'Queued'}
                  </span>
                  <span className="font-mono text-white">{progress}%</span>
                </div>
                <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: stageColor }}
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ ease: 'easeOut', duration: 0.5 }}
                  />
                </div>

                {/* Stage pills */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {STAGES.filter(s => s.id !== 'completed').map((s) => {
                    const isActive = s.id === (stage || 'queued')
                    const isDone = progress > s.range[1]
                    return (
                      <div
                        key={s.id}
                        className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border transition-all ${
                          isActive
                            ? 'border-transparent text-white'
                            : isDone
                            ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                            : 'border-zinc-800 text-zinc-600'
                        }`}
                        style={isActive ? { backgroundColor: `${s.color}20`, borderColor: `${s.color}50`, color: s.color } : {}}
                      >
                        {isDone && !isActive ? (
                          <CheckCircle className="h-3 w-3 text-emerald-400" />
                        ) : isActive ? (
                          <s.icon className="h-3 w-3 animate-pulse" />
                        ) : (
                          <s.icon className="h-3 w-3 opacity-30" />
                        )}
                        {s.label}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Failed state */}
            {isFailed && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 space-y-3">
                <div className="flex items-start gap-2.5">
                  <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-red-400">Ingestion failed</p>
                    {processingStatus?.error && (
                      <p className="text-xs text-red-400/70 mt-1 font-mono">{processingStatus.error}</p>
                    )}
                    {processingStatus?.retry_count > 0 && (
                      <p className="text-xs text-zinc-500 mt-1">Attempted {processingStatus.retry_count} time(s)</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={async () => {
                    try {
                      const { retryDocumentProcessing } = await import('../services/api')
                      await retryDocumentProcessing(queued.document_id, user?.id)
                      setProcessingStatus({ status: 'queued', progress: 0, stage: 'queued' })
                    } catch (err) {
                      setError('Failed to retry processing')
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 text-red-300
                             border border-red-500/30 hover:bg-red-500/30 transition-colors text-sm"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Retry Processing
                </button>
              </div>
            )}

            {/* Retrying banner */}
            {statusLabel === 'retrying' && (
              <div className="flex items-center gap-2.5 rounded-xl border border-orange-500/20 bg-orange-500/10 px-4 py-3 text-sm text-orange-400">
                <RefreshCw className="h-4 w-4 animate-spin" />
                Retrying… attempt {processingStatus?.retry_count || 1} of 3
              </div>
            )}

            {/* Job metadata */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              {[
                ['Document ID', queued.document_id],
                ['Job ID',      queued.job_id],
              ].map(([label, value]) => (
                <div key={label} className="space-y-0.5">
                  <p className="text-zinc-600 text-xs uppercase tracking-wider">{label}</p>
                  <p className="font-mono text-xs text-zinc-500 truncate">{value}</p>
                </div>
              ))}
            </div>

            <p className="text-zinc-600 text-xs text-center">
              You can safely navigate away. Processing continues in the background.
            </p>
          </div>
        </motion.div>
      </div>
    )
  }

  /* ══════════════════════════════════════════════
     UPLOAD FORM
  ══════════════════════════════════════════════ */
  return (
    <div className="px-6 py-10">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
        className="max-w-5xl mx-auto mb-8"
      >
        <h1 className="text-4xl font-bold tracking-tight mb-2">Upload Documents</h1>
        <p className="text-zinc-400">
          Upload PDF documents for instant queuing — embedding happens in the background, no waiting.
        </p>
      </motion.div>

      {/* Upload Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.05 }}
        className="max-w-5xl mx-auto"
      >
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-8 space-y-6">

          {/* Dropzone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="rounded-xl border-2 border-dashed border-zinc-700
                       p-12 md:p-14 text-center cursor-pointer
                       hover:border-zinc-500 hover:bg-zinc-800/40
                       transition-all duration-200"
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            <div className="flex flex-col items-center gap-5">
              <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-zinc-800 flex-shrink-0">
                <Upload className="h-7 w-7 text-zinc-300" />
              </div>
              <div className="space-y-1">
                <p className="font-medium text-lg text-white">
                  {file ? file.name : 'Drop your PDF here'}
                </p>
                <p className="text-zinc-500 text-sm">
                  {file
                    ? `${(file.size / 1024 / 1024).toFixed(2)} MB`
                    : 'PDF files only · max 25 MB · ingested in the background'}
                </p>
              </div>

              {/* File upload progress bar (multipart transfer) */}
              {uploading && (
                <div className="w-full max-w-xs mt-1">
                  <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
                    <span>Uploading file</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <motion.div
                      className="h-full bg-white rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                      transition={{ ease: 'easeOut', duration: 0.3 }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* File preview + remove */}
          <AnimatePresence>
            {file && !uploading && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/50 px-4 py-3"
              >
                <FileText className="h-5 w-5 text-zinc-400 flex-shrink-0" />
                <p className="flex-1 text-sm text-zinc-300 truncate">{file.name}</p>
                <span className="text-xs text-zinc-500">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                <button
                  onClick={() => { setFile(null); setUploadProgress(0); setError(null) }}
                  className="flex-shrink-0 p-1.5 rounded-md hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
                  aria-label="Remove file"
                >
                  <X className="h-4 w-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Collection selector */}
          <div className="space-y-2 max-w-xl">
            <p className="text-sm font-medium text-zinc-300">Collection</p>
            <div ref={collectionsRef} className="relative">
              <button
                type="button"
                onClick={() => setCollectionsOpen(!collectionsOpen)}
                className="flex items-center gap-2 w-full h-11 rounded-lg border border-zinc-800 bg-zinc-800/60
                           px-4 text-sm text-white hover:bg-zinc-800/80 transition-colors"
              >
                <Folder className="h-4 w-4 text-zinc-500 flex-shrink-0" />
                <span className="flex-1 text-left truncate">
                  {collectionsLoading
                    ? 'Loading…'
                    : selectedUploadCollection
                      ? (collections.find(c => c.id === selectedUploadCollection)?.name || 'default')
                      : 'Select a collection (or default)'}
                </span>
                <ChevronDown className={`h-4 w-4 text-zinc-500 flex-shrink-0 transition-transform ${collectionsOpen ? 'rotate-180' : ''}`} />
              </button>

              {collectionsOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                  className="absolute z-50 top-full left-0 right-0 mt-1.5 rounded-xl border border-zinc-800
                             bg-zinc-900 shadow-xl shadow-black/40 overflow-hidden"
                >
                  {/* Default */}
                  <button
                    type="button"
                    onClick={() => { setSelectedUploadCollection(''); setCollectionsOpen(false) }}
                    className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm transition-colors hover:bg-zinc-800
                               ${!selectedUploadCollection ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                  >
                    <Folder className="h-3.5 w-3.5 text-zinc-500" />
                    <span className="flex-1 text-left">default</span>
                  </button>
                  <div className="h-px bg-zinc-800" />

                  {collections.length === 0 && !collectionsLoading && (
                    <p className="px-3.5 py-2.5 text-xs text-zinc-600">No collections yet</p>
                  )}
                  {collections.map((col) => (
                    <button
                      key={col.id}
                      type="button"
                      onClick={() => { setSelectedUploadCollection(col.id); setCollectionsOpen(false) }}
                      className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm transition-colors hover:bg-zinc-800
                                 ${selectedUploadCollection === col.id ? 'bg-white/5 text-white' : 'text-zinc-300'}`}
                    >
                      <Folder className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
                      <span className="flex-1 truncate">{col.name}</span>
                      <span className="text-xs text-zinc-600">{col.total_documents || 0} docs</span>
                    </button>
                  ))}

                  <div className="h-px bg-zinc-800" />

                  {/* Inline new collection */}
                  <AnimatePresence>
                    {showNewCollection ? (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden px-3 py-2 space-y-2"
                      >
                        <input
                          autoFocus
                          type="text"
                          placeholder="Collection name…"
                          value={newCollectionName}
                          onChange={(e) => setNewCollectionName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleCreateCollection()
                            if (e.key === 'Escape') setShowNewCollection(false)
                          }}
                          className="w-full h-9 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-white/20"
                        />
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleCreateCollection}
                            disabled={creatingCollection || !newCollectionName.trim()}
                            className="h-8 px-3 rounded-lg bg-white text-black text-xs font-medium hover:bg-zinc-200 transition-colors disabled:opacity-40 flex items-center gap-1"
                          >
                            {creatingCollection ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                            Create
                          </button>
                          <button
                            type="button"
                            onClick={() => { setShowNewCollection(false); setNewCollectionName('') }}
                            className="h-8 px-3 rounded-lg bg-zinc-800 text-zinc-300 text-xs hover:bg-zinc-700 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </motion.div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setShowNewCollection(true)}
                        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        New collection
                      </button>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </div>
          </div>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                className="flex items-start gap-3 rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-400"
              >
                <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Upload button */}
          <button
            onClick={handleSubmit}
            disabled={!file || uploading}
            className="w-full h-11 rounded-xl bg-white text-black font-medium
                       hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all active:scale-[0.99] flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading {uploadProgress > 0 && `${uploadProgress}%`}
              </>
            ) : (
              <>
                <FileUp className="h-4 w-4" />
                Upload Document
              </>
            )}
          </button>

          {/* Async info notice */}
          <p className="text-zinc-600 text-xs text-center flex items-center justify-center gap-1.5">
            <Zap className="h-3 w-3" />
            Upload returns instantly — embedding &amp; indexing happen in the background
          </p>
        </div>
      </motion.div>

      <p className="text-zinc-600 text-sm text-center mt-6 max-w-5xl mx-auto">
        Maximum file size 25 MB · PDF only
      </p>
    </div>
  )
}
