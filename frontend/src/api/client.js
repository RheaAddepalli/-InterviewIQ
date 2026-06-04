import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// ── Sessions ─────────────────────────────────────────────────

export const startSession = (formData) =>
  api.post('/sessions/start', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const getSession = (sessionId) =>
  api.get(`/sessions/${sessionId}`)

export const completeSession = (sessionId) =>
  api.post(`/sessions/${sessionId}/complete`)

export const getReport = (sessionId) =>
  api.get(`/sessions/${sessionId}/report`)

// ── Interview ─────────────────────────────────────────────────

export const nextQuestion = (sessionId) =>
  api.post(`/sessions/${sessionId}/next-question`)

export const submitAnswer = (sessionId, payload) =>
  api.post(`/sessions/${sessionId}/answer`, payload)

// ── Misc ──────────────────────────────────────────────────────

export const getRoles = () => api.get('/roles')

export const ingestKnowledge = (role) =>
  api.post('/knowledge/ingest', null, { params: { role } })

export const knowledgeStatus = () => api.get('/knowledge/status')
