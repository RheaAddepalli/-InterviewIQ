import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import InterviewPage from './pages/InterviewPage'
import ReportPage from './pages/ReportPage'

export default function App() {
  return (
    <Routes>
      <Route path="/"          element={<UploadPage />} />
      <Route path="/interview" element={<InterviewPage />} />
      <Route path="/report"    element={<ReportPage />} />
      <Route path="*"          element={<Navigate to="/" replace />} />
    </Routes>
  )
}
