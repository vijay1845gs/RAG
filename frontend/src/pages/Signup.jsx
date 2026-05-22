import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, UserPlus, User, AlertCircle, Loader2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function Signup() {
  const navigate = useNavigate()
  const { signup, authLoading } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

const handleSubmit = async (e) => {
  e.preventDefault()
  setError(null); setSuccess(null)
  if (password.length < 6) { setError('Password must be at least 6 characters.'); return }
  try {
    await signup(email, password, fullName)
    setSuccess('Account created! Check your email to confirm your signup, then sign in.')
    setEmail(''); setPassword(''); setFullName('')
    // Redirect to login page after successful signup (email confirmation required)
    setTimeout(() => navigate('/login', { replace: true }), 1500)
  } catch (err) {
    setError(err?.message || 'Sign-up failed. Please try again.')
  }
}

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="w-full max-w-sm"
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Create account</h1>
          <p className="text-zinc-500 text-sm mt-1">Start building with RAG</p>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 space-y-4">
          {error && (
            <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 rounded-lg border border-red-500/25
                         bg-red-500/10 px-4 py-3 text-sm text-red-400"
            >
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.div>
          )}
          {success && (
            <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 rounded-lg border border-emerald-500/25
                         bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400"
            >
              <span>{success}</span>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Full name */}
            <div className="space-y-1.5">
              <label htmlFor="signup-name" className="text-sm font-medium text-zinc-300">Full name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  id="signup-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  autoComplete="name"
                  className="w-full h-10 rounded-lg border border-zinc-800 bg-zinc-800/60
                             pl-9 pr-4 text-sm text-white placeholder-zinc-600
                             focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-600
                             transition-all"
                />
              </div>
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label htmlFor="signup-email" className="text-sm font-medium text-zinc-300">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  id="signup-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  className="w-full h-10 rounded-lg border border-zinc-800 bg-zinc-800/60
                             pl-9 pr-4 text-sm text-white placeholder-zinc-600
                             focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-600
                             transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label htmlFor="signup-pw" className="text-sm font-medium text-zinc-300">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  id="signup-pw"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  autoComplete="new-password"
                  className="w-full h-10 rounded-lg border border-zinc-800 bg-zinc-800/60
                             pl-9 pr-4 text-sm text-white placeholder-zinc-600
                             focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-600
                             transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={authLoading}
              className="w-full h-10 rounded-xl bg-white text-black text-sm font-medium
                         hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all active:scale-[0.97] flex items-center justify-center gap-2"
            >
              {authLoading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</>
              ) : (
                <><UserPlus className="h-4 w-4" /> Create Account</>
              )}
            </button>
          </form>

          <p className="text-xs text-zinc-600 text-center pt-1">
            Already have an account?{' '}
            <Link to="/login" className="text-white hover:underline">Sign in</Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}
