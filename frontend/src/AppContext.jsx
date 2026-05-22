import { createContext, useContext, useState, useCallback, useEffect } from 'react'

const AppContext = createContext(null)

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}

/* ════════════════════════════════════════════════════ PROVIDER */
export function AppProvider({ children }) {
  const [uploads, setUploads] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('uploads')
      try {
        return saved ? JSON.parse(saved) : []
      } catch {
        return []
      }
    }
    return []
  })
  const [chatHistory, setChatHistory] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('chatHistory')
      try {
        return saved ? JSON.parse(saved) : []
      } catch {
        return []
      }
    }
    return []
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('uploads', JSON.stringify(uploads))
      } catch (e) {
        console.error('Failed to save uploads to localStorage', e)
      }
    }
  }, [uploads])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('chatHistory', JSON.stringify(chatHistory))
      } catch (e) {
        console.error('Failed to save chatHistory to localStorage', e)
      }
    }
  }, [chatHistory])

  const recordUpload = useCallback((doc) => {
    setUploads((prev) => [doc, ...prev])
  }, [])

  const removeUpload = useCallback((documentId) => {
    setUploads((prev) => prev.filter((d) => d.document_id !== documentId))
  }, [])

  const addChatTurn = useCallback((turn) => {
    setChatHistory((prev) => [turn, ...prev])
  }, [])

  const clearChatHistory = useCallback(() => {
    setChatHistory([])
  }, [])

  return (
    <AppContext.Provider value={{
      uploads, chatHistory,
      recordUpload, removeUpload,
      addChatTurn, clearChatHistory,
    }}>
    {children}
  </AppContext.Provider>
  )
}