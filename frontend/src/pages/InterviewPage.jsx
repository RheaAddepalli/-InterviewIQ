import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Loader2, Brain, Clock, ChevronRight, Tag } from 'lucide-react'
import clsx from 'clsx'
// import { nextQuestion, submitAnswer, completeSession } from '../../api/client'
import { nextQuestion, submitAnswer, completeSession } from "../api/client";
import { useInterviewStore } from '../store/interviewStore'

const DIFFICULTY_COLORS = {
  easy:   'bg-green-500/20 text-green-400',
  medium: 'bg-amber-500/20 text-amber-400',
  hard:   'bg-red-500/20 text-red-400',
}
const TYPE_COLORS = {
  conceptual: 'bg-purple-500/20 text-purple-300',
  applied:    'bg-blue-500/20 text-blue-300',
  scenario:   'bg-teal-500/20 text-teal-300',
  follow_up:  'bg-orange-500/20 text-orange-300',
}

export default function InterviewPage() {
  const navigate = useNavigate()
  const {
    sessionId,
    sessionMeta,
    currentQuestion,
    questionHistory,
    totalQuestions,
    questionsAsked,
    setCurrentQuestion,
    pushAnswer,
    setLoading,
    setError,
    setReport,
    // setQuestionsAsked,
  } = useInterviewStore()

  const [answer, setAnswer] = useState('')
  const [loadingQ, setLoadingQ] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [startTime, setStartTime] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef(null)
  const textareaRef = useRef(null)

  // Redirect if no session
  useEffect(() => {
    if (!sessionId) navigate('/')
  }, [sessionId])

  // Load first question on mount
  useEffect(() => {
    if (sessionId && !currentQuestion && questionsAsked === 0) {
      fetchNextQuestion()
    }
  }, [sessionId])

  // Timer
  useEffect(() => {
    if (currentQuestion) {
      setStartTime(Date.now())
      setElapsed(0)
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - Date.now()) / 1000))
      }, 1000)
    }
    return () => clearInterval(timerRef.current)
  }, [currentQuestion?.question_id])

  const fetchNextQuestion = async () => {
    setLoadingQ(true)
    try {
      const { data } = await nextQuestion(sessionId)
      if (data.done) {
        await handleFinish()
        return
      }
      setCurrentQuestion(data)
      // setQuestionsAsked(1)
      setAnswer('')
      setStartTime(Date.now())
      textareaRef.current?.focus()
    } catch (err) {
      setError('Failed to load next question.')
    } finally {
      setLoadingQ(false)
    }
  }

  const handleSubmit = async () => {
    if (!answer.trim() || !currentQuestion) return
    setSubmitting(true)
    const duration = startTime ? Math.floor((Date.now() - startTime) / 1000) : 0
    try {
     

      const { data } = await submitAnswer(
        sessionId,
        {
          question_id: currentQuestion.question_id,
          answer_text: answer.trim(),
          duration_sec: duration,
        }
      )

      pushAnswer(
        currentQuestion.question_id,
        answer.trim()
      )

      // ============================================================
      // Adaptive next question already returned by backend
      // ============================================================
      if (data.status === "completed") {

        await handleFinish()

        return
      }

      if (data.next_question) {
        // setQuestionsAsked(questionsAsked + 1)
        // setCurrentQuestion({

        //   question_id:
        //     data.next_question.question_id,

        //   question_text:
        //     data.next_question.question_text,

        //   difficulty:
        //     data.next_question.difficulty,

        //   topic:
        //     data.next_question.topic,

        //   question_type:
        //     data.strategy?.question_type,

        //   is_follow_up:
        //     data.strategy?.is_follow_up,
        // })
        setCurrentQuestion(data.next_question)

        setAnswer("")

        setStartTime(Date.now())

        textareaRef.current?.focus()

      } else {

        await handleFinish()
      }

    } catch {
      setError('Failed to submit answer.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleFinish = async () => {
    await completeSession(sessionId)
    navigate('/report')
  }

  const progress = Math.round((questionsAsked / totalQuestions) * 100)

  return (
    <div className="min-h-screen flex flex-col max-w-3xl mx-auto px-4 py-8 gap-6">

      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center">
            <Brain className="w-4 h-4 text-brand-400" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Role</p>
            <p className="text-sm font-medium text-white">{sessionMeta?.role}</p>
          </div>
        </div>

        <div className="text-right">
          <p className="text-xs text-slate-500">Progress</p>
          <p className="text-sm font-medium text-white">
            {questionsAsked} / {totalQuestions}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-600 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Question history (compact) */}
      {questionHistory.length > 0 && (
        <div className="space-y-2">
          {questionHistory.slice(-2).map((item, i) => (
            <div key={i} className="card bg-slate-900/50 opacity-60 text-sm space-y-1 py-3">
              <p className="text-slate-400 font-medium line-clamp-1">Q: {item.question}</p>
              <p className="text-slate-500 line-clamp-1">A: {item.answer || '—'}</p>
            </div>
          ))}
        </div>
      )}

      {/* Current question card */}
      {loadingQ ? (
        <div className="card flex-1 flex items-center justify-center gap-3 text-slate-400 min-h-[200px]">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Generating question...</span>
        </div>
      ) : currentQuestion ? (
        <div className="card flex-1 space-y-4">
          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            {currentQuestion.topic && (
              <span className={clsx('badge', 'bg-slate-800 text-slate-300')}>
                <Tag className="w-3 h-3 inline mr-1" />{currentQuestion.topic}
              </span>
            )}
            {currentQuestion.difficulty && (
              <span className={clsx('badge', DIFFICULTY_COLORS[currentQuestion.difficulty])}>
                {currentQuestion.difficulty}
              </span>
            )}
            {currentQuestion.question_type && (
              <span className={clsx('badge', TYPE_COLORS[currentQuestion.question_type])}>
                {currentQuestion.question_type}
              </span>
            )}
            {currentQuestion.is_follow_up && (
              <span className="badge bg-orange-500/20 text-orange-300">↪ follow-up</span>
            )}
          </div>

          {/* Question text */}
          <p className="text-lg text-white leading-relaxed font-medium">
            {currentQuestion.question_text}
          </p>

          {/* Answer textarea */}
          <div className="space-y-2 pt-2">
            <label className="text-xs text-slate-500 uppercase tracking-wide">Your answer</label>
            <textarea
              ref={textareaRef}
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
              }}
              rows={5}
              placeholder="Type your answer here... (Ctrl+Enter to submit)"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3
                         text-slate-200 placeholder-slate-600 resize-none focus:outline-none
                         focus:border-brand-500 transition-colors text-sm"
            />
          </div>

          {/* Submit */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-slate-600">
              {answer.length > 0 ? `${answer.trim().split(/\s+/).length} words` : ''}
            </span>
            <button
              onClick={handleSubmit}
              disabled={!answer.trim() || submitting}
              className="btn-primary flex items-center gap-2"
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  Submit & Next
                  <ChevronRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      ) : null}

      {/* Skip / finish early */}
      <div className="flex justify-end">
        <button onClick={handleFinish} className="btn-ghost text-xs">
          End interview & see report →
        </button>
      </div>
    </div>
  )
}
