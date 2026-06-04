import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart2, CheckCircle, AlertTriangle, Star,
  ChevronDown, ChevronUp, RotateCcw, Loader2
} from 'lucide-react'
import clsx from 'clsx'
// import { getReport } from '../../api/client'
import { getReport } from "../api/client";
// import { useInterviewStore } from '../../store/interviewStore'
import { useInterviewStore } from '../store/interviewStore'
const RECOMMENDATION_STYLES = {
  'strong hire': 'text-green-400 bg-green-500/20 border-green-500/30',
  'hire':        'text-green-300 bg-green-500/10 border-green-500/20',
  'consider':    'text-amber-400 bg-amber-500/20 border-amber-500/30',
  'pass':        'text-red-400   bg-red-500/20   border-red-500/30',
}

function ScoreRing({ label, value }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-16 h-16">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none"
            stroke="rgb(30,41,59)" strokeWidth="3.5" />
          <circle cx="18" cy="18" r="15.9" fill="none"
            stroke="rgb(99,102,241)" strokeWidth="3.5"
            strokeDasharray={`${value * 10}, 100`}
            strokeLinecap="round" />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center
                         text-white font-bold text-sm">{value}</span>
      </div>
      <span className="text-xs text-slate-500 text-center">{label}</span>
    </div>
  )
}

export default function ReportPage() {
  const navigate = useNavigate()
  const { sessionId, questionHistory, reset } = useInterviewStore()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    if (!sessionId) { navigate('/'); return }
    getReport(sessionId)
      .then(r => setReport(r.data))
      .catch(() => setReport(null))
      .finally(() => setLoading(false))
  }, [sessionId])

  const analysis = report?.analysis || {}
  const session  = report?.session  || {}

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span>Generating your report...</span>
      </div>
    )
  }

  return (
    <div className="min-h-screen max-w-3xl mx-auto px-4 py-10 space-y-6">

      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart2 className="w-6 h-6 text-brand-400" />
          Interview Report
        </h1>
        <p className="text-slate-400 text-sm">
          {session.candidate_name || 'Candidate'} · {session.role}
        </p>
      </div>

      {/* Recommendation badge */}
      {analysis.recommendation && (
        <div className={clsx(
          'inline-flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold',
          RECOMMENDATION_STYLES[analysis.recommendation] || RECOMMENDATION_STYLES['consider']
        )}>
          <Star className="w-4 h-4" />
          {analysis.recommendation.toUpperCase()}
        </div>
      )}

      {/* Scores */}
      <div className="card">
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-4">Scores</p>
        <div className="flex gap-8 justify-center">
          <ScoreRing label="Technical depth"   value={analysis.depth_score || 0} />
          <ScoreRing label="Communication"     value={analysis.communication_score || 0} />
          <ScoreRing label="Questions answered" value={session.questions_asked || 0} />
        </div>
      </div>

      {/* Overview */}
      {analysis.overall_assessment && (
        <div className="card space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Overall assessment</p>
          <p className="text-slate-200 leading-relaxed">{analysis.overall_assessment}</p>
        </div>
      )}

      {/* Strengths / Gaps */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card space-y-3">
          <p className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5 text-green-400" /> Strengths
          </p>
          <ul className="space-y-1.5">
            {(analysis.strengths || []).map((s, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-green-400 mt-0.5">✓</span> {s}
              </li>
            ))}
          </ul>
        </div>
        <div className="card space-y-3">
          <p className="text-xs text-slate-500 uppercase tracking-wide flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Areas to improve
          </p>
          <ul className="space-y-1.5">
            {(analysis.gaps || []).map((g, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">△</span> {g}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Topics covered */}
      {(analysis.topics_covered || []).length > 0 && (
        <div className="card space-y-3">
          <p className="text-xs text-slate-500 uppercase tracking-wide">Topics covered</p>
          <div className="flex flex-wrap gap-2">
            {analysis.topics_covered.map((t, i) => (
              <span key={i} className="badge bg-slate-800 text-slate-300">{t}</span>
            ))}
          </div>
        </div>
      )}

      {/* Q&A Transcript */}
      <div className="card space-y-4">
        <p className="text-xs text-slate-500 uppercase tracking-wide">Full transcript</p>
        {(report?.questions || questionHistory).map((item, i) => {
          const isExp = expanded[i]
          const qText = item.question_text || item.question
          const aText = item.answer_text   || item.answer
          return (
            <div key={i} className="border border-slate-800 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpanded(prev => ({ ...prev, [i]: !isExp }))}
                className="w-full flex items-center justify-between px-4 py-3
                           text-left hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <span className="text-brand-400 font-bold text-sm mt-0.5">Q{i + 1}</span>
                  <span className="text-slate-200 text-sm line-clamp-1">{qText}</span>
                </div>
                {isExp
                  ? <ChevronUp className="w-4 h-4 text-slate-500 flex-shrink-0" />
                  : <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />
                }
              </button>
              {isExp && (
                <div className="px-4 pb-4 space-y-3 border-t border-slate-800 pt-3">
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Question</p>
                    <p className="text-slate-200 text-sm">{qText}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 mb-1">Answer</p>
                    <p className="text-slate-300 text-sm whitespace-pre-wrap">
                      {aText || '(no answer given)'}
                    </p>
                  </div>
                  {(item.topic || item.difficulty) && (
                    <div className="flex gap-2 pt-1">
                      {item.topic && (
                        <span className="badge bg-slate-800 text-slate-400">{item.topic}</span>
                      )}
                      {item.difficulty && (
                        <span className="badge bg-slate-800 text-slate-400">{item.difficulty}</span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Reset */}
      <div className="flex justify-center pb-6">
        <button onClick={() => { reset(); navigate('/') }} className="btn-ghost flex items-center gap-2">
          <RotateCcw className="w-4 h-4" />
          Start new interview
        </button>
      </div>
    </div>
  )
}
