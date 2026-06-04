import React, { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, ChevronRight, Briefcase, AlertCircle, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
// import { startSession, getRoles } from '../../api/client'
import { startSession, getRoles } from "../api/client";
import { useInterviewStore } from '../store/interviewStore'

export default function UploadPage() {
  const navigate = useNavigate()
  const setSession = useInterviewStore(s => s.setSession)

  const [roles, setRoles] = useState([])
  const [selectedRole, setSelectedRole] = useState('')
  const [experienceLevel, setExperienceLevel] = useState('junior')
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getRoles().then(r => setRoles(r.data.roles)).catch(() => {})
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer?.files?.[0] || e.target.files?.[0]
    if (f && (f.type === 'application/pdf' || f.name.endsWith('.txt'))) {
      setFile(f)
      setError('')
    } else {
      setError('Please upload a PDF or TXT file.')
    }
  }, [])

  const handleSubmit = async () => {
    if (!file || !selectedRole) {
      setError('Please select a role and upload your resume.')
      return
    }
    setUploading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('resume', file)
      form.append('role', selectedRole)
      form.append(
  'experience_level',
  experienceLevel
)
      const { data } = await startSession(form)
      setSession(data.session_id, data)
      navigate('/interview')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start session. Is the backend running?')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl space-y-6">

        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-600/20 mb-2">
            <Briefcase className="w-7 h-7 text-brand-500" />
          </div>
          <h1 className="text-3xl font-bold text-white">AI Technical Interviewer</h1>
          <p className="text-slate-400 text-sm">
            Upload your resume, select a role — get a personalised interview
          </p>
        </div>

        {/* Role selection */}
        <div className="card space-y-3">
          <label className="text-sm font-medium text-slate-300">Target role</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(
              roles.length
                ? roles
                : [
                    'AI/ML Engineer',
                    'Data Scientist',
                    'Deep Learning Engineer',
                  ]
            ).map(role => (
              <button
                key={role}
                onClick={() => setSelectedRole(role)}
                className={clsx(
                  'text-left px-4 py-3 rounded-xl border text-sm font-medium transition-all',
                  selectedRole === role
                    ? 'border-brand-500 bg-brand-600/20 text-brand-300'
                    : 'border-slate-700 hover:border-slate-500 text-slate-400 hover:text-white'
                )}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
        {/* Experience level */}
        <div className="card space-y-3">
          <label className="text-sm font-medium text-slate-300">
            Experience level
          </label>

          <select
            value={experienceLevel}
            onChange={(e) => setExperienceLevel(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 text-white"
          >
            <option value="junior">Fresher / Student</option>
            <option value="junior">Junior (0-2 years)</option>
            <option value="mid">Mid-Level (2-5 years)</option>
            <option value="senior">Senior (5+ years)</option>
          </select>
        </div>

        {/* Resume upload */}
        <div className="card space-y-3">
          <label className="text-sm font-medium text-slate-300">Resume (PDF or TXT)</label>
          <div
            onDrop={onDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => document.getElementById('file-input').click()}
            className={clsx(
              'border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all',
              dragOver
                ? 'border-brand-500 bg-brand-600/10'
                : file
                  ? 'border-green-500/50 bg-green-500/5'
                  : 'border-slate-700 hover:border-slate-500'
            )}
          >
            <input
              id="file-input"
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={onDrop}
            />
            {file ? (
              <div className="flex items-center justify-center gap-3 text-green-400">
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">{file.name}</span>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="w-8 h-8 mx-auto text-slate-500" />
                <p className="text-slate-400 text-sm">
                  Drag & drop or <span className="text-brand-400 underline">browse</span>
                </p>
                <p className="text-slate-600 text-xs">PDF or TXT — max 10MB</p>
              </div>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* CTA */}
        <button
          onClick={handleSubmit}
          disabled={uploading || !file || !selectedRole}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3"
        >
          {uploading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin rounded-full w-4 h-4 border-2 border-white border-t-transparent" />
              Parsing resume...
            </span>
          ) : (
            <>
              Start Interview
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}
