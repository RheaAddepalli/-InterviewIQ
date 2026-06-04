import { create } from 'zustand'

export const useInterviewStore = create((set, get) => ({
  // Session state
  sessionId: null,
  sessionMeta: null,     // { role, candidate_name, experience_level, skills, domains }
  status: 'idle',        // idle | uploading | active | completed

  // Interview state
  currentQuestion: null,
  questionHistory: [],   // [{ question, answer, topic, difficulty, question_id }]
  totalQuestions: 10,
  questionsAsked: 0,

  // Report
  report: null,

  // UI
  isLoading: false,
  error: null,

  // ── Actions ─────────────────────────────────────────────────
  setSession: (id, meta) => set({
    sessionId: id,
    sessionMeta: meta,
    status: 'active',
    totalQuestions: meta.total_questions || 10,
    questionsAsked: 0,
    questionHistory: [],
    currentQuestion: null,
    error: null,
  }),

  setCurrentQuestion: (q) => set({
  currentQuestion: q,
  questionsAsked: q.order_index || 1,
  isLoading: false,
}),

  pushAnswer: (questionId, answerText) => {
    const { currentQuestion, questionHistory } = get()
    if (!currentQuestion) return
    set({
      questionHistory: [
        ...questionHistory,
        {
          question_id: questionId || currentQuestion.question_id,
          question:    currentQuestion.question_text,
          answer:      answerText,
          topic:       currentQuestion.topic,
          difficulty:  currentQuestion.difficulty,
          order_index: currentQuestion.order_index,
        },
      ],
      currentQuestion: null,
    })
  },

  setReport: (report) => set({ report, status: 'completed' }),

  setLoading: (v)   => set({ isLoading: v }),
  setError:   (msg) => set({ error: msg, isLoading: false }),
  clearError: ()    => set({ error: null }),

  reset: () => set({
    sessionId: null, sessionMeta: null, status: 'idle',
    currentQuestion: null, questionHistory: [], report: null,
    totalQuestions: 10, questionsAsked: 0,
    isLoading: false, error: null,
  }),
}))
