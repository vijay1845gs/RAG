import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  MessageSquare,
  FileText,
  History,
  Settings,
  LogOut,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function AppLayout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, profile, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  // Get display name: profile.full_name > email username
  const displayName = profile?.full_name || (user?.email ? user.email.split('@')[0] : 'User')
  const email = user?.email || ''

  // Get initials for avatar
  const getInitials = (name) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) || 'U'
  }

  const initials = getInitials(displayName)

  return (
    <div className="min-h-screen bg-black text-white">
      {/* ── Global Navbar ── */}
      <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
          {/* Left: Logo + Nav Items */}
          <div className="flex items-center gap-1">
            {/* App Title */}
            <div className="flex items-center gap-2 px-2 py-1 mr-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/10">
                <LayoutDashboard className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-sm font-semibold text-white hidden sm:inline">RAG App</span>
            </div>

            {/* Nav Links */}
            <div className="flex items-center gap-1">
              {nav.map(({ to, icon: Icon, label }) => {
                const active = pathname === to || (to !== '/' && pathname.startsWith(to))
                return (
                  <NavLink
                    key={to}
                    to={to}
                    className={`
                      relative flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium
                      transition-colors
                      ${active
                        ? 'text-white bg-white/10'
                        : 'text-zinc-400 hover:text-white hover:bg-white/5'
                      }
                    `}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="hidden sm:inline">{label}</span>
                  </NavLink>
                )
              })}
            </div>
          </div>

          {/* Right: User Profile + Logout */}
          <div className="flex items-center gap-3">
            {/* User Profile Card */}
            <div className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-white/5 transition-colors">
              {/* Avatar */}
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-700 text-xs font-medium text-white">
                {initials}
              </div>
              {/* User Info - hidden on mobile */}
              <div className="hidden sm:block text-left">
                <p className="text-sm font-medium text-white leading-tight">{displayName}</p>
                <p className="text-xs text-zinc-500 leading-tight">{email}</p>
              </div>
            </div>

            {/* Logout Button */}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </nav>

      {/* ── Page content ── */}
      <Outlet />
    </div>
  )
}