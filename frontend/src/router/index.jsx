import { createBrowserRouter, Navigate } from 'react-router-dom'

import AppLayout from '../components/AppLayout'
import ProtectedRoute from '../components/ProtectedRoute'

import Login from '../pages/Login'
import Signup from '../pages/Signup'
import Upload from '../pages/Upload'
import Chat from '../pages/Chat'
import Dashboard from '../pages/Dashboard'
import Documents from '../pages/Documents'
import ChatHistory from '../pages/History'
import SettingsPage from '../pages/Settings'

const router = createBrowserRouter([
  /* ─────────────────────────────────────────
     Public Auth Routes (No Navbar)
   ───────────────────────────────────────── */
  {
    path: '/login',
    element: <Login />,
  },

  {
    path: '/signup',
    element: <Signup />,
  },

  /* ─────────────────────────────────────────
     Protected App Routes (With Navbar)
   ───────────────────────────────────────── */
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          /* Default Route → Dashboard */
          {
            index: true,
            element: <Navigate to="/dashboard" replace />,
          },

          {
            path: 'dashboard',
            element: <Dashboard />,
          },

          {
            path: 'upload',
            element: <Upload />,
          },

          {
            path: 'chat',
            element: <Chat />,
          },

          {
            path: 'chat/:sessionId',
            element: <Chat />,
          },

          {
            path: 'documents',
            element: <Documents />,
          },

          {
            path: 'history',
            element: <ChatHistory />,
          },

          {
            path: 'settings',
            element: <SettingsPage />,
          },
        ],
      },
    ],
  },

  /* Fallback Route */
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
])

export default router