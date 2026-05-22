import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings, Brain, Database, User, AlertTriangle,
  LayoutDashboard, RefreshCw, Trash2, LogOut, Check,
  Loader2, ChevronRight, Shield,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useApp } from '../AppContext'
import { useSettings } from '../contexts/SettingsContext'
import {
  fetchChatSession,
  fetchCollections,
  fetchChatSessions,
} from '../services/api'

const asArray = (value) => (Array.isArray(value) ? value : [])

/* ─── Toast ─── */
function Toast({ status }) {
  const map = {
    saving: { bg: 'bg-zinc-800 border-zinc-700', text: 'text-zinc-300', msg: 'Saving…', icon: <Loader2 className="h-3.5 w-3.5 animate-spin" /> },
    saved:  { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', msg: 'Saved ✓', icon: <Check className="h-3.5 w-3.5" /> },
    error:  { bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400', msg: 'Save failed', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  }
  const t = map[status]
  if (!t) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.96 }}
      className={`fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl border ${t.bg} ${t.text} text-sm font-medium shadow-2xl backdrop-blur-xl`}
    >
      {t.icon} {t.msg}
    </motion.div>
  )
}

/* ─── Section wrapper ─── */
function Section({ icon: Icon, title, subtitle, color = 'from-zinc-500 to-zinc-600', children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-zinc-800/80 bg-zinc-900/60 backdrop-blur-sm overflow-hidden"
    >
      <div className="flex items-center gap-3 px-6 py-4 border-b border-zinc-800/60">
        <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          {subtitle && <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="p-6 space-y-5">{children}</div>
    </motion.div>
  )
}

/* ─── Toggle ─── */
function Toggle({ value, onChange, label, description }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-zinc-200">{label}</p>
        {description && <p className="text-xs text-zinc-500 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative h-6 w-11 rounded-full transition-colors duration-200 flex-shrink-0 ${value ? 'bg-white' : 'bg-zinc-700'}`}
      >
        <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-black shadow transition-transform duration-200 ${value ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  )
}

/* ─── Slider ─── */
function Slider({ value, onChange, min, max, step = 1, label, description, format }) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-200">{label}</p>
          {description && <p className="text-xs text-zinc-500 mt-0.5">{description}</p>}
        </div>
        <span className="text-sm font-mono font-medium text-white px-2.5 py-1 rounded-lg bg-zinc-800 border border-zinc-700">
          {format ? format(value) : value}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-zinc-800">
        <div className="absolute left-0 top-0 h-full rounded-full bg-white/90 transition-all" style={{ width: `${pct}%` }} />
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
    </div>
  )
}

/* ─── Chips ─── */
function ChipGroup({ value, onChange, options }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(o => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            value === o.value
              ? 'bg-white text-black'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 border border-zinc-700'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ─── Confirmation Modal ─── */
function ConfirmModal({ open, title, message, onConfirm, onCancel, danger = true }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl"
      >
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl mb-4 ${danger ? 'bg-red-500/10' : 'bg-zinc-800'}`}>
          <AlertTriangle className={`h-5 w-5 ${danger ? 'text-red-400' : 'text-zinc-400'}`} />
        </div>
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <p className="text-sm text-zinc-400 mt-2 leading-relaxed">{message}</p>
        <div className="flex gap-3 mt-5">
          <button onClick={onCancel} className="flex-1 h-10 rounded-xl bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 transition-colors">Cancel</button>
          <button
            onClick={onConfirm}
            className={`flex-1 h-10 rounded-xl text-sm font-medium transition-colors ${danger ? 'bg-red-500 hover:bg-red-600 text-white' : 'bg-white hover:bg-zinc-100 text-black'}`}
          >Confirm</button>
        </div>
      </motion.div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════ */
export default function SettingsPage() {
  const { user, profile, logout } = useAuth()
  const { clearChatHistory } = useApp()
  const { settings, loading, saveStatus, update, reset } = useSettings()

  const [collections, setCollections] = useState([])
  const [stats, setStats] = useState({ chats: 0, collections: 0 })
  const [modal, setModal] = useState(null) // null | 'reset' | 'clearHistory' | 'logout'

  const fullName = profile?.full_name || user?.user_metadata?.full_name || 'User'
  const email = user?.email || ''
  const joined = user?.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : '—'
  const initials = fullName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)

  /* ─── Load collections + stats ─── */
  useEffect(() => {
    if (!user?.id) return
    fetchCollections(user.id)
      .then(r => {
        const cols = Array.isArray(r.data) ? r.data : []
        setCollections(cols)
        setStats(s => ({ ...s, collections: cols.length }))
      })
      .catch(() => {})
    fetchChatSessions(user.id)
      .then(async r => {
        const sessions = asArray(r.data)
        const messages = await Promise.all(
          sessions.map(async (session) => {
            try {
              const detail = await fetchChatSession(session.id, user.id)
              return asArray(detail.data?.messages)
            } catch {
              return []
            }
          })
        )
        const chatTurns = messages.reduce((total, items) => total + items.length, 0)
        setStats(s => ({ ...s, chats: chatTurns }))
      })
      .catch(() => {})
  }, [user?.id])

  const handleLogout = async () => {
    await logout()
    clearChatHistory()
  }

  /* ─── Token estimate ─── */
  const estimatedTokens = Math.round((settings.max_context_chunks * settings.chunk_size) / 4)

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="flex items-center gap-3 text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading settings…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-black text-white">
      <AnimatePresence>{saveStatus && <Toast status={saveStatus} />}</AnimatePresence>

      <div className="max-w-2xl mx-auto px-5 py-10 flex flex-col gap-5">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-zinc-700 to-zinc-900 border border-zinc-700">
            <Settings className="h-5 w-5 text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
            <p className="text-zinc-500 text-sm">Personalize your AI workspace</p>
          </div>
        </motion.div>

        {/* ─── SECTION 1: Profile ─── */}
        <Section icon={User} title="Profile" subtitle="Your account information" color="from-violet-500 to-purple-600">
          {/* Avatar + info */}
          <div className="flex items-center gap-4 p-4 rounded-xl bg-zinc-800/50 border border-zinc-800">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/30 to-purple-600/20 border border-violet-500/20 text-xl font-bold text-violet-300 flex-shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-white truncate">{fullName}</p>
              <p className="text-sm text-zinc-400 truncate">{email}</p>
              <p className="text-xs text-zinc-600 mt-1">Member since {joined}</p>
            </div>
          </div>
          {/* Stats */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Chat Turns', value: stats.chats, icon: '💬' },
              { label: 'Collections', value: stats.collections, icon: '📁' },
            ].map(s => (
              <div key={s.label} className="rounded-xl bg-zinc-800/50 border border-zinc-800 p-4 text-center">
                <p className="text-2xl mb-1">{s.icon}</p>
                <p className="text-2xl font-bold text-white">{s.value}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* ─── SECTION 2: Workspace ─── */}
        <Section icon={LayoutDashboard} title="Workspace" subtitle="UI and chat behavior" color="from-blue-500 to-cyan-600">
          <div className="space-y-1">
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Theme</p>
            <ChipGroup
              value={settings.theme}
              onChange={v => update({ theme: v })}
              options={[{ value: 'dark', label: '🌙 Dark' }, { value: 'light', label: '☀️ Light' }, { value: 'system', label: '⚙️ System' }]}
            />
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Default Collection</p>
            <select
              value={settings.default_collection_id || ''}
              onChange={e => update({ default_collection_id: e.target.value || null })}
              className="w-full h-10 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-white/20"
            >
              <option value="">None (use last selected)</option>
              {collections.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <div className="divide-y divide-zinc-800/60 space-y-0">
            <div className="py-3"><Toggle value={settings.auto_scroll} onChange={v => update({ auto_scroll: v })} label="Auto-scroll" description="Automatically scroll to latest message" /></div>
            <div className="py-3"><Toggle value={settings.show_sources} onChange={v => update({ show_sources: v })} label="Show Sources" description="Display retrieved document citations" /></div>
            <div className="py-3"><Toggle value={settings.save_chat_history} onChange={v => update({ save_chat_history: v })} label="Save Chat History" description="Persist conversations to database" /></div>
          </div>
        </Section>

        {/* ─── SECTION 3: AI Behavior ─── */}
        <Section icon={Brain} title="AI Behavior" subtitle="Model and response configuration" color="from-emerald-500 to-teal-600">
          <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Model</p>
            <ChipGroup
              value={settings.preferred_model}
              onChange={v => update({ preferred_model: v })}
              options={[
                { value: 'gemini', label: '✦ Gemini' },
                { value: 'gpt', label: '⬡ GPT' },
                { value: 'claude', label: '◆ Claude' },
                { value: 'local', label: '⚙ Local LLM' },
              ]}
            />
          </div>

          <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">RAG Mode</p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { v: 'precise', label: 'Precise', desc: 'top_k=3, temp=0.1', emoji: '🎯' },
                { v: 'balanced', label: 'Balanced', desc: 'top_k=5, temp=0.3', emoji: '⚖️' },
                { v: 'creative', label: 'Creative', desc: 'top_k=8, temp=0.8', emoji: '🎨' },
              ].map(m => (
                <button
                  key={m.v}
                  onClick={() => update({ rag_mode: m.v })}
                  className={`p-3 rounded-xl border text-left transition-all ${settings.rag_mode === m.v ? 'border-white/30 bg-white/5' : 'border-zinc-800 bg-zinc-800/40 hover:border-zinc-700'}`}
                >
                  <p className="text-lg mb-1">{m.emoji}</p>
                  <p className="text-sm font-semibold text-white">{m.label}</p>
                  <p className="text-[10px] text-zinc-500 mt-0.5 font-mono">{m.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Response Style</p>
            <ChipGroup
              value={settings.response_style}
              onChange={v => update({ response_style: v })}
              options={[
                { value: 'professional', label: 'Professional' },
                { value: 'concise', label: 'Concise' },
                { value: 'beginner_friendly', label: 'Beginner' },
                { value: 'research', label: 'Research' },
                { value: 'technical', label: 'Technical' },
              ]}
            />
          </div>

          <Slider
            value={settings.temperature}
            onChange={v => update({ temperature: v })}
            min={0} max={2} step={0.05}
            label="Temperature"
            description="Controls creativity vs. determinism"
            format={v => v.toFixed(2)}
          />
        </Section>

        {/* ─── SECTION 4: Retrieval ─── */}
        <Section icon={Database} title="Retrieval Settings" subtitle="RAG pipeline configuration" color="from-amber-500 to-orange-600">
          <Slider
            value={settings.max_context_chunks}
            onChange={v => update({ max_context_chunks: v })}
            min={1} max={20}
            label="Max Context Chunks"
            description="Number of document chunks retrieved per query"
          />
          <Slider
            value={settings.chunk_size}
            onChange={v => update({ chunk_size: v })}
            min={200} max={4000} step={100}
            label="Chunk Size"
            description="Characters per chunk during document processing"
            format={v => `${v} chars`}
          />
          <Slider
            value={settings.chunk_overlap}
            onChange={v => update({ chunk_overlap: Math.min(v, settings.chunk_size - 50) })}
            min={0} max={Math.max(0, settings.chunk_size - 50)} step={50}
            label="Chunk Overlap"
            description="Overlap between consecutive chunks"
            format={v => `${v} chars`}
          />
          {/* Token estimate */}
          <div className="flex items-center justify-between rounded-xl bg-amber-500/5 border border-amber-500/15 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-amber-400">Estimated Token Usage</p>
              <p className="text-xs text-zinc-500 mt-0.5">Per query context window</p>
            </div>
            <span className="text-xl font-bold text-amber-400 font-mono">~{estimatedTokens.toLocaleString()}</span>
          </div>
        </Section>

        {/* ─── SECTION 5: Danger Zone ─── */}
        <Section icon={Shield} title="Danger Zone" subtitle="Irreversible actions" color="from-red-500 to-rose-600">
          <div className="space-y-3">
            <button
              onClick={() => setModal('reset')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-zinc-700 bg-zinc-800/50 hover:bg-zinc-800 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <RefreshCw className="h-4 w-4 text-zinc-400 group-hover:text-zinc-300" />
                <div className="text-left">
                  <p className="text-sm font-medium text-zinc-200">Reset Settings</p>
                  <p className="text-xs text-zinc-500">Restore all settings to factory defaults</p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-zinc-600" />
            </button>

            <button
              onClick={() => setModal('clearHistory')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <Trash2 className="h-4 w-4 text-red-400" />
                <div className="text-left">
                  <p className="text-sm font-medium text-red-400">Delete All Chat History</p>
                  <p className="text-xs text-zinc-500">Permanently delete all conversation sessions</p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-red-500/40" />
            </button>

            <button
              onClick={() => setModal('logout')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl border border-zinc-700 bg-zinc-800/50 hover:bg-zinc-800 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <LogOut className="h-4 w-4 text-zinc-400" />
                <div className="text-left">
                  <p className="text-sm font-medium text-zinc-200">Log Out</p>
                  <p className="text-xs text-zinc-500">Sign out of your account</p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-zinc-600" />
            </button>
          </div>
        </Section>

        <p className="text-center text-xs text-zinc-700 pb-4">
          Settings are synced to your account and persist across devices.
        </p>
      </div>

      {/* Modals */}
      <ConfirmModal
        open={modal === 'reset'}
        title="Reset Settings?"
        message="All settings will be restored to factory defaults. This cannot be undone."
        onConfirm={async () => { await reset(); setModal(null) }}
        onCancel={() => setModal(null)}
      />
      <ConfirmModal
        open={modal === 'clearHistory'}
        title="Delete All Chat History?"
        message="Every conversation and message will be permanently deleted. This action cannot be undone."
        onConfirm={() => { clearChatHistory(); setModal(null) }}
        onCancel={() => setModal(null)}
      />
      <ConfirmModal
        open={modal === 'logout'}
        title="Log Out?"
        message="You'll be signed out of your account."
        danger={false}
        onConfirm={handleLogout}
        onCancel={() => setModal(null)}
      />
    </div>
  )
}
