import { AuthProvider } from './contexts/AuthContext'
import { AppProvider } from './AppContext'
import { SettingsProvider } from './contexts/SettingsContext'
import { RouterProvider } from 'react-router-dom'
import router from './router'

export default function App() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <AppProvider>
          <RouterProvider router={router} />
        </AppProvider>
      </SettingsProvider>
    </AuthProvider>
  )
}
