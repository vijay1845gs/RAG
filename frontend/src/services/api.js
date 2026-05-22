import axios from 'axios'

const BASE_URL = 'http://localhost:8000'

/* ─── Upload ─────────────────────────────────────────────────── */
export async function submitUpload(formData, onProgress, userId = null) {
  if (userId) {
    formData.append('user_id', userId)
  }
  return axios.post(`${BASE_URL}/api/v1/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total) onProgress && onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
}

/* ─── Chat / RAG ─────────────────────────────────────────────── */
export async function submitChat(body) {
  return axios.post(`${BASE_URL}/api/v1/chat`, body)
}

/* ─── Health ─────────────────────────────────────────────────── */
export async function checkHealth() {
  return axios.get(`${BASE_URL}/health`)
}

/* ─── Documents ────────────────────────────────────────────────── */
export async function fetchDocuments(userId, collectionId) {
  const params = new URLSearchParams()
  if (userId) params.append('user_id', userId)
  if (collectionId) params.append('collection_id', collectionId)
  return axios.get(`${BASE_URL}/api/v1/documents?${params.toString()}`)
}

export async function fetchDocument(documentId, userId) {
  return axios.get(`${BASE_URL}/api/v1/documents/${documentId}?user_id=${userId}`)
}

export async function deleteDocument(documentId, userId) {
  return axios.delete(`${BASE_URL}/api/v1/documents/${documentId}?user_id=${userId}`)
}

/* ─── Collections ──────────────────────────────────────────────── */
export async function createCollection(userId, name, description = '') {
  const params = new URLSearchParams({ user_id: userId, name, description })
  return axios.post(`${BASE_URL}/api/v1/collections?${params.toString()}`)
}

export async function fetchCollections(userId) {
  return axios.get(`${BASE_URL}/api/v1/collections?user_id=${userId}`)
}

export async function renameCollection(collectionId, userId, name) {
  return axios.patch(`${BASE_URL}/api/v1/collections/${collectionId}?user_id=${userId}`, { name })
}

export async function deleteCollection(collectionId, userId) {
  return axios.delete(`${BASE_URL}/api/v1/collections/${collectionId}?user_id=${userId}`)
}

/* ─── Chat History ───────────────────────────────────────────── */
export async function fetchChatSessions(userId) {
  return axios.get(`${BASE_URL}/api/v1/chat/sessions?user_id=${userId}`)
}

export async function fetchChatSession(sessionId, userId) {
  return axios.get(`${BASE_URL}/api/v1/chat/sessions/${sessionId}?user_id=${userId}`)
}

export async function createChatSession(userId, title = 'New Conversation') {
  const params = new URLSearchParams({ user_id: userId, title })
  return axios.post(`${BASE_URL}/api/v1/chat/sessions`, {}, { params })
}

export async function saveChatMessage(data) {
  return axios.post(`${BASE_URL}/api/v1/chat/messages`, data)
}

export async function deleteChatSession(sessionId, userId) {
  return axios.delete(`${BASE_URL}/api/v1/chat/sessions/${sessionId}?user_id=${userId}`)
}

/* ─── Settings ──────────────────────────────────────────────── */
export async function fetchSettings(userId) {
  return axios.get(`${BASE_URL}/api/v1/settings/${userId}`)
}

export async function updateSettings(userId, patch) {
  return axios.patch(`${BASE_URL}/api/v1/settings/${userId}`, patch)
}

export async function resetSettings(userId) {
  return axios.post(`${BASE_URL}/api/v1/settings/${userId}/reset`)
}

/* ─── Phase 7: Async Processing ─────────────────────────────── */

/**
 * Poll document processing status.
 * Returns: { status, progress, stage, job_id, error, retry_count }
 *
 * Adaptive polling intervals:
 *   queued:     5 seconds
 *   processing: 3 seconds
 *   retrying:   4 seconds
 *   completed:  stop
 *   failed:     stop
 */
export async function fetchDocumentStatus(documentId, userId) {
  const params = userId ? `?user_id=${userId}` : ''
  return axios.get(`${BASE_URL}/api/v1/documents/${documentId}/status${params}`)
}

/**
 * Re-enqueue a failed document for reprocessing.
 * Only works when processing_status === 'failed'.
 */
export async function retryDocumentProcessing(documentId, userId) {
  const params = userId ? `?user_id=${userId}` : ''
  return axios.post(`${BASE_URL}/api/v1/documents/${documentId}/retry${params}`)
}

/**
 * Fetch queue intelligence stats for the Dashboard.
 * Returns: { queued_jobs, active_jobs, failed_jobs, completion_rate, cache, worker }
 */
export async function fetchQueueStats(userId) {
  const params = userId ? `?user_id=${userId}` : ''
  return axios.get(`${BASE_URL}/api/v1/queue/stats${params}`)
}
