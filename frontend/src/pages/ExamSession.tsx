/**
 * pages/ExamSession.tsx
 * Supports dual exam modes:
 * 1. Live Entrance Exam (JEE / NEET / CAT mode):
 *    - Full Question Palette (jump, Mark for Review, Clear Response)
 *    - Negative marking (+4 / -1)
 *    - No instant feedback / spoilers during exam
 *    - Final submit modal
 * 2. Adaptive Practice Exam:
 *    - Dynamic Thompson Sampling question sequencing
 *    - Immediate feedback & AI tutor explanations
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'
import { useCameraProctoring } from '../hooks/useCameraProctoring'
import MathText from '../components/MathText'

interface SessionDetail {
  id: string
  domain: string
  skill?: string
  max_questions: number
  time_limit_seconds?: number
  status: string
  exam_type: 'live' | 'practice'
  positive_mark: number
  negative_mark: number
  exam_paper_title?: string
}

interface PaletteItem {
  sequence_number: number
  question_id: string
  review_status: 'not_visited' | 'not_answered' | 'answered' | 'marked_for_review' | 'answered_and_marked'
  selected_option: string | null
  status: string
}

interface CurrentQuestion {
  sequence_number: number
  question_id: string
  question_text: string
  options: Record<string, string>
  domain: string
  skill: string
  difficulty: number
  selected_option: string | null
  review_status: string
}

interface AdaptiveQuestion {
  question_id: string
  question: string
  domain: string
  skill: string
  difficulty: number
  options: Record<string, string>
}

interface AttemptResult {
  is_correct: boolean
  correct_answer: string
  explanation: string
}

type Phase = 'loading' | 'question' | 'feedback' | 'finishing' | 'error'

export default function ExamSession() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const { videoRef, cameraError, hasPermission, sendEvent } = useCameraProctoring(sessionId)

  const [session, setSession] = useState<SessionDetail | null>(null)
  const [phase, setPhase] = useState<Phase>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  // Live Exam Palette State
  const [palette, setPalette] = useState<PaletteItem[]>([])
  const [activeSeq, setActiveSeq] = useState<number>(1)
  const [liveQuestion, setLiveQuestion] = useState<CurrentQuestion | null>(null)
  const [selectedLiveOption, setSelectedLiveOption] = useState<string | null>(null)
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [savingAnswer, setSavingAnswer] = useState(false)

  // Adaptive Practice State
  const [adaptiveQuestion, setAdaptiveQuestion] = useState<AdaptiveQuestion | null>(null)
  const [answeredCount, setAnsweredCount] = useState(0)
  const [selectedAdaptiveOption, setSelectedAdaptiveOption] = useState<string | null>(null)
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [submittingAdaptive, setSubmittingAdaptive] = useState(false)

  const questionStartRef = useRef<number>(Date.now())

  // Window focus monitoring
  useEffect(() => {
    const handleBlur = () => {
      sendEvent('focus_lost', 'medium', 1.0, { reason: 'window_blur' })
    }
    window.addEventListener('blur', handleBlur)
    return () => window.removeEventListener('blur', handleBlur)
  }, [sendEvent])

  // Load session
  const loadSession = useCallback(async () => {
    const res = await client.get(`/exam-sessions/${sessionId}`)
    return res.data as SessionDetail
  }, [sessionId])

  // Load Palette for Live Exam
  const loadPalette = useCallback(async () => {
    const res = await client.get(`/exam-sessions/${sessionId}/live-palette`)
    return res.data.palette as PaletteItem[]
  }, [sessionId])

  // Load Live Question by Sequence Number
  const loadLiveQuestion = useCallback(async (seq: number) => {
    const res = await client.get(`/exam-sessions/${sessionId}/question-by-seq/${seq}`)
    const data = res.data as CurrentQuestion
    setLiveQuestion(data)
    setSelectedLiveOption(data.selected_option || null)
    setActiveSeq(seq)
    questionStartRef.current = Date.now()
  }, [sessionId])

  // Fetch next Adaptive Question
  const loadNextAdaptiveQuestion = useCallback(async (sId: string) => {
    const res = await client.get(`/exam-sessions/${sId}/next-question`)
    const data = res.data
    return {
      question_id: data.id,
      question: data.question_text,
      domain: data.domain,
      skill: data.skill,
      difficulty: data.difficulty,
      options: data.options
    } as AdaptiveQuestion
  }, [])

  // Initial loader
  useEffect(() => {
    const init = async () => {
      setPhase('loading')
      try {
        const s = await loadSession()
        setSession(s)

        if (s.exam_type === 'live') {
          const pal = await loadPalette()
          setPalette(pal)
          if (pal.length > 0) {
            await loadLiveQuestion(1)
          }
          setPhase('question')
        } else {
          // Adaptive mode
          const q = await loadNextAdaptiveQuestion(s.id)
          setAdaptiveQuestion(q)
          questionStartRef.current = Date.now()
          setPhase('question')
        }
      } catch (err: unknown) {
        const e = err as Error
        setErrorMsg(e.message || 'Failed to initialize session.')
        setPhase('error')
      }
    }
    init()
  }, [loadSession, loadPalette, loadLiveQuestion, loadNextAdaptiveQuestion])

  // Proctoring telemetry
  useEffect(() => {
    if (!session || phase !== 'question') return

    const reportEvent = (eventType: string) => {
      client.post('/proctoring-events', {
        exam_session_id: session.id,
        event_type: eventType,
        severity: 'medium',
        confidence: 1.0
      }).catch(() => {})
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') reportEvent('tab_switch')
    }
    const handleBlur = () => reportEvent('focus_lost')
    const handlePaste = (e: ClipboardEvent) => {
      reportEvent('clipboard_paste')
      e.preventDefault()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('blur', handleBlur)
    window.addEventListener('paste', handlePaste)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('blur', handleBlur)
      window.removeEventListener('paste', handlePaste)
    }
  }, [session, phase])

  // ---- LIVE EXAM HANDLERS ----

  const handleSaveAndNext = async (markForReview = false) => {
    if (!liveQuestion || !session || savingAnswer) return
    setSavingAnswer(true)
    const timeSpent = Math.round((Date.now() - questionStartRef.current) / 1000)

    let reviewStatus = 'not_answered'
    if (selectedLiveOption) {
      reviewStatus = markForReview ? 'answered_and_marked' : 'answered'
    } else {
      reviewStatus = markForReview ? 'marked_for_review' : 'not_answered'
    }

    try {
      await client.post(`/exam-sessions/${session.id}/live-answer`, {
        question_id: liveQuestion.question_id,
        selected_option: selectedLiveOption,
        review_status: reviewStatus,
        time_taken: timeSpent
      })

      // Update palette locally
      setPalette((prev) =>
        prev.map((item) =>
          item.sequence_number === activeSeq
            ? { ...item, review_status: reviewStatus as PaletteItem['review_status'], selected_option: selectedLiveOption }
            : item
        )
      )

      // Move to next sequence if available
      if (activeSeq < palette.length) {
        await loadLiveQuestion(activeSeq + 1)
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to save answer')
    } finally {
      setSavingAnswer(false)
    }
  }

  const handleClearResponse = async () => {
    if (!liveQuestion || !session || savingAnswer) return
    setSavingAnswer(true)
    try {
      await client.post(`/exam-sessions/${session.id}/live-answer`, {
        question_id: liveQuestion.question_id,
        selected_option: null,
        review_status: 'not_answered'
      })
      setSelectedLiveOption(null)
      setPalette((prev) =>
        prev.map((item) =>
          item.sequence_number === activeSeq
            ? { ...item, review_status: 'not_answered', selected_option: null }
            : item
        )
      )
    } catch {
      alert('Failed to clear response')
    } finally {
      setSavingAnswer(false)
    }
  }

  const jumpToQuestion = async (targetSeq: number) => {
    if (targetSeq === activeSeq || savingAnswer) return
    // Auto-save current choice before jumping if changed
    if (liveQuestion && selectedLiveOption !== liveQuestion.selected_option) {
      await client.post(`/exam-sessions/${sessionId}/live-answer`, {
        question_id: liveQuestion.question_id,
        selected_option: selectedLiveOption,
        review_status: selectedLiveOption ? 'answered' : 'not_answered'
      }).catch(() => {})
    }
    await loadLiveQuestion(targetSeq)
  }

  // ---- ADAPTIVE PRACTICE HANDLERS ----

  const handleAdaptiveAnswer = async (optionKey: string) => {
    if (!adaptiveQuestion || !session || submittingAdaptive) return
    setSelectedAdaptiveOption(optionKey)
    setSubmittingAdaptive(true)
    const timeTaken = Math.round((Date.now() - questionStartRef.current) / 1000)

    try {
      const res = await client.post('/question-attempts', {
        question_id: adaptiveQuestion.question_id,
        selected_answer: optionKey,
        time_taken: timeTaken,
        exam_session_id: session.id,
      })
      setAttemptResult(res.data as AttemptResult)
      setAnsweredCount((c) => c + 1)
      setPhase('feedback')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setErrorMsg(axiosErr.response?.data?.detail || 'Failed to submit answer.')
      setPhase('error')
    } finally {
      setSubmittingAdaptive(false)
    }
  }

  const handleAdaptiveContinue = async () => {
    if (!session) return
    if (answeredCount >= session.max_questions) {
      await finishSession()
      return
    }
    setPhase('loading')
    setSelectedAdaptiveOption(null)
    setAttemptResult(null)
    try {
      const q = await loadNextAdaptiveQuestion(session.id)
      setAdaptiveQuestion(q)
      questionStartRef.current = Date.now()
      setPhase('question')
    } catch (err: unknown) {
      const e = err as Error
      setErrorMsg(e.message)
      setPhase('error')
    }
  }

  const finishSession = async () => {
    if (!session) return
    setPhase('finishing')
    try {
      await client.post(`/exam-sessions/${session.id}/finish`)
      navigate(`/exam/results/${session.id}`)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setErrorMsg(axiosErr.response?.data?.detail || 'Failed to finish session.')
      setPhase('error')
    }
  }

  // Palette counts for Live Exam summary
  const answeredCountLive = palette.filter((p) => p.selected_option !== null).length
  const markedReviewCount = palette.filter((p) => p.review_status === 'marked_for_review' || p.review_status === 'answered_and_marked').length
  const notAnsweredCount = palette.length - answeredCountLive

  if (phase === 'error') {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-6 bg-red-50 border border-red-300 rounded-lg">
        <h2 className="text-lg font-semibold text-red-800 mb-2">Error</h2>
        <p className="text-red-700">{errorMsg}</p>
        <button
          onClick={() => navigate('/exam/setup')}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
        >
          Back to Setup
        </button>
      </div>
    )
  }

  if (phase === 'loading' || phase === 'finishing' || !session) {
    return (
      <div className="flex flex-col justify-center items-center h-64 gap-3">
        <Spinner size="lg" />
        <p className="text-gray-500 text-sm">
          {phase === 'finishing' ? 'Submitting & computing scores...' : 'Loading exam paper...'}
        </p>
      </div>
    )
  }

  // =========================================================================
  // 1. LIVE ENTRANCE EXAM UI (JEE / NEET / CAT FORMAT)
  // =========================================================================
  if (session.exam_type === 'live') {
    return (
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Top Header Bar */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm flex flex-wrap justify-between items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg">🏛️</span>
              <h1 className="text-lg font-bold text-gray-900">
                {session.exam_paper_title || `${session.domain} Live Entrance Exam`}
              </h1>
              <span className="text-xs bg-indigo-100 text-indigo-800 font-bold px-2 py-0.5 rounded">
                Standardized Paper
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Identical question paper • Question Palette Active • Negative Marking (+{session.positive_mark} / -{session.negative_mark})
            </p>
          </div>

          {/* Camera proctoring pill */}
          <div className="flex items-center gap-3">
            <div className="flex items-center text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse mr-1.5" />
              Webcam Proctor Active
            </div>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-16 h-12 object-cover rounded border border-gray-300 shadow-sm"
            />
            <button
              onClick={() => setShowSubmitModal(true)}
              className="bg-red-600 hover:bg-red-700 text-white font-bold text-xs px-4 py-2 rounded shadow transition-colors"
            >
              Submit Exam
            </button>
          </div>
        </div>

        {/* Main Grid: Question (Left 70%) & Question Palette (Right 30%) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Question Panel */}
          <div className="lg:col-span-8 bg-white border border-gray-200 rounded-lg p-6 shadow-sm space-y-6">
            {liveQuestion ? (
              <>
                <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                  <span className="font-bold text-gray-800 text-base">
                    Question {liveQuestion.sequence_number} of {palette.length}
                  </span>
                  <div className="flex gap-2">
                    <span className="text-xs font-semibold px-2 py-1 bg-green-100 text-green-800 rounded">
                      +{session.positive_mark} Marks
                    </span>
                    <span className="text-xs font-semibold px-2 py-1 bg-red-100 text-red-800 rounded">
                      -{session.negative_mark} Negative Mark
                    </span>
                  </div>
                </div>

                <div className="text-gray-900 text-base leading-relaxed font-medium">
                  <MathText text={liveQuestion.question_text} />
                </div>

                {/* Options List */}
                <div className="space-y-3 pt-2">
                  {Object.entries(liveQuestion.options).map(([key, text]) => {
                    const isSelected = selectedLiveOption === key
                    return (
                      <div
                        key={key}
                        onClick={() => setSelectedLiveOption(key)}
                        className={`flex items-start gap-3 p-3.5 rounded-lg border-2 cursor-pointer transition-all ${
                          isSelected
                            ? 'border-indigo-600 bg-indigo-50/60 shadow-sm'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold mt-0.5 border ${
                            isSelected
                              ? 'bg-indigo-600 text-white border-indigo-600'
                              : 'bg-white text-gray-600 border-gray-400'
                          }`}
                        >
                          {key}
                        </div>
                        <div className="text-gray-800 text-sm font-normal"><MathText text={text} /></div>
                      </div>
                    )
                  })}
                </div>

                {/* Action Buttons: Save & Next, Mark for Review, Clear Response */}
                <div className="pt-6 border-t border-gray-100 flex flex-wrap justify-between items-center gap-2">
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveAndNext(false)}
                      disabled={savingAnswer}
                      className="px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white font-medium text-xs rounded-md shadow-sm transition-colors"
                    >
                      Save & Next
                    </button>
                    <button
                      onClick={() => handleSaveAndNext(true)}
                      disabled={savingAnswer}
                      className="px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-medium text-xs rounded-md shadow-sm transition-colors"
                    >
                      Mark for Review & Next
                    </button>
                    <button
                      onClick={handleClearResponse}
                      disabled={savingAnswer || !selectedLiveOption}
                      className="px-3.5 py-2.5 border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium text-xs rounded-md transition-colors disabled:opacity-40"
                    >
                      Clear Response
                    </button>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => jumpToQuestion(activeSeq - 1)}
                      disabled={activeSeq <= 1}
                      className="px-3.5 py-2 border border-gray-300 text-gray-600 hover:bg-gray-50 text-xs font-medium rounded-md disabled:opacity-40"
                    >
                      ← Previous
                    </button>
                    <button
                      onClick={() => jumpToQuestion(activeSeq + 1)}
                      disabled={activeSeq >= palette.length}
                      className="px-3.5 py-2 border border-gray-300 text-gray-600 hover:bg-gray-50 text-xs font-medium rounded-md disabled:opacity-40"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex justify-center items-center h-48">
                <Spinner size="md" />
              </div>
            )}
          </div>

          {/* Question Palette Sidebar */}
          <div className="lg:col-span-4 bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-5">
            <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wide border-b pb-2">
              Question Palette
            </h2>

            {/* Legend */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-green-500 text-white text-[10px] flex items-center justify-center font-bold">
                  {answeredCountLive}
                </span>
                <span className="text-gray-600">Answered</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-red-500 text-white text-[10px] flex items-center justify-center font-bold">
                  {notAnsweredCount}
                </span>
                <span className="text-gray-600">Not Answered</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-purple-600 text-white text-[10px] flex items-center justify-center font-bold">
                  {markedReviewCount}
                </span>
                <span className="text-gray-600">Marked for Review</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-gray-200 text-gray-700 text-[10px] flex items-center justify-center font-bold">
                  •
                </span>
                <span className="text-gray-600">Not Visited</span>
              </div>
            </div>

            {/* Palette Grid Numbers (1 to N) */}
            <div className="border rounded-lg p-3 bg-gray-50 max-h-72 overflow-y-auto">
              <div className="grid grid-cols-5 gap-2">
                {palette.map((item) => {
                  const isActive = item.sequence_number === activeSeq
                  let bg = 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  if (item.review_status === 'answered' || (item.selected_option && item.review_status !== 'answered_and_marked')) {
                    bg = 'bg-green-500 text-white font-bold'
                  } else if (item.review_status === 'marked_for_review') {
                    bg = 'bg-purple-600 text-white font-bold'
                  } else if (item.review_status === 'answered_and_marked') {
                    bg = 'bg-purple-600 text-white font-bold border-2 border-green-400'
                  } else if (item.review_status === 'not_answered') {
                    bg = 'bg-red-500 text-white font-bold'
                  }

                  return (
                    <button
                      key={item.sequence_number}
                      onClick={() => jumpToQuestion(item.sequence_number)}
                      className={`h-9 rounded text-xs transition-all flex items-center justify-center ${bg} ${
                        isActive ? 'ring-2 ring-indigo-700 ring-offset-2 scale-105' : ''
                      }`}
                    >
                      {item.sequence_number}
                    </button>
                  )
                })}
              </div>
            </div>

            <button
              onClick={() => setShowSubmitModal(true)}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-md shadow transition-colors"
            >
              Submit Final Test
            </button>
          </div>
        </div>

        {/* Confirmation Modal */}
        {showSubmitModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-xl space-y-4">
              <h3 className="text-lg font-bold text-gray-900">Confirm Exam Submission</h3>
              <p className="text-sm text-gray-600">
                Are you sure you want to finish the exam? Once submitted, you cannot change your answers.
              </p>

              <div className="bg-gray-50 border rounded-lg p-3 text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Questions:</span>
                  <span className="font-bold">{palette.length}</span>
                </div>
                <div className="flex justify-between text-green-700">
                  <span>Answered:</span>
                  <span className="font-bold">{answeredCountLive}</span>
                </div>
                <div className="flex justify-between text-purple-700">
                  <span>Marked for Review:</span>
                  <span className="font-bold">{markedReviewCount}</span>
                </div>
                <div className="flex justify-between text-red-600">
                  <span>Not Answered:</span>
                  <span className="font-bold">{notAnsweredCount}</span>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowSubmitModal(false)}
                  className="px-4 py-2 border border-gray-300 text-gray-700 text-xs font-medium rounded hover:bg-gray-50"
                >
                  Return to Test
                </button>
                <button
                  onClick={finishSession}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded shadow"
                >
                  Yes, Submit Exam
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // =========================================================================
  // 2. ADAPTIVE PRACTICE EXAM UI (AI TUTOR & REAL-TIME FEEDBACK)
  // =========================================================================
  if (!adaptiveQuestion) return null
  const progress = Math.round((answeredCount / session.max_questions) * 100)
  const optionKeys = Object.keys(adaptiveQuestion.options)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Proctoring camera feed */}
      <div className="flex justify-between items-center bg-gray-100 rounded-lg p-3">
        <div className="text-sm text-gray-600">
          {hasPermission ? (
            <span className="flex items-center text-green-600 gap-1 text-xs">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              Camera active (Proctoring)
            </span>
          ) : cameraError ? (
            <span className="text-red-600 text-xs">{cameraError}</span>
          ) : (
            <span className="text-xs">Requesting camera access...</span>
          )}
        </div>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`w-28 h-20 object-cover rounded shadow border ${
            hasPermission ? 'border-green-300' : 'border-gray-300'
          }`}
        />
      </div>

      {/* Header: session info + progress */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
        <div className="flex justify-between items-center mb-3">
          <div>
            <span className="text-sm font-bold text-blue-700">Adaptive Practice Mode</span>
            <span className="mx-2 text-gray-300">|</span>
            <span className="text-sm text-gray-500">{session.domain}</span>
          </div>
          <span className="text-xs text-gray-500">
            {answeredCount} / {session.max_questions} answered
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Question card */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 space-y-6">
        <div className="flex justify-between items-start">
          <span className="text-xs text-blue-600 uppercase font-bold tracking-wide">
            Adaptive Difficulty: {adaptiveQuestion.difficulty?.toFixed(2) ?? 'Dynamic'}
          </span>
        </div>

        <p className="text-gray-800 text-base leading-relaxed font-medium">
          <MathText text={adaptiveQuestion.question} />
        </p>

        {phase === 'question' && (
          <div className="grid grid-cols-1 gap-3">
            {optionKeys.map((key) => (
              <button
                key={key}
                onClick={() => handleAdaptiveAnswer(key)}
                disabled={submittingAdaptive}
                className="flex items-start gap-3 w-full text-left px-4 py-3 border border-gray-300 rounded-md hover:border-blue-500 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50 transition-colors"
              >
                <span className="font-semibold text-blue-600 min-w-[1.5rem]">{key}.</span>
                <span className="text-gray-700"><MathText text={adaptiveQuestion.options[key]} /></span>
              </button>
            ))}
          </div>
        )}

        {/* Real-time Feedback & AI Explanation */}
        {phase === 'feedback' && attemptResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3">
              {optionKeys.map((key) => {
                const isCorrect = key === attemptResult.correct_answer
                const isSelected = key === selectedAdaptiveOption
                let cls = 'flex items-start gap-3 w-full text-left px-4 py-3 border rounded-md cursor-default'
                if (isCorrect) cls += ' border-green-500 bg-green-50'
                else if (isSelected && !isCorrect) cls += ' border-red-400 bg-red-50'
                else cls += ' border-gray-200 opacity-60'
                return (
                  <div key={key} className={cls}>
                    <span
                      className={`font-semibold min-w-[1.5rem] ${
                        isCorrect ? 'text-green-600' : isSelected ? 'text-red-500' : 'text-gray-400'
                      }`}
                    >
                      {key}.
                    </span>
                    <span className="text-gray-700"><MathText text={adaptiveQuestion.options[key]} /></span>
                    {isCorrect && <span className="ml-auto text-green-600 text-xs font-semibold">Correct</span>}
                    {isSelected && !isCorrect && (
                      <span className="ml-auto text-red-500 text-xs font-semibold">Your choice</span>
                    )}
                  </div>
                )
              })}
            </div>

            <div
              className={`p-4 rounded-md border ${
                attemptResult.is_correct ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'
              }`}
            >
              <p
                className={`font-semibold mb-1 ${
                  attemptResult.is_correct ? 'text-green-800' : 'text-red-800'
                }`}
              >
                {attemptResult.is_correct ? '✨ Correct Answer!' : '❌ Incorrect'}
              </p>
              {attemptResult.explanation && (
                <p className="text-xs text-gray-700 leading-relaxed mt-1">
                  💡 <strong>Explanation:</strong> <MathText text={attemptResult.explanation} />
                </p>
              )}
            </div>

            <div className="flex justify-between items-center pt-2">
              <span className="text-xs text-gray-500">
                {session.max_questions - answeredCount} questions remaining
              </span>
              <button
                onClick={handleAdaptiveContinue}
                className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-md hover:bg-blue-700 transition-colors shadow"
              >
                {answeredCount >= session.max_questions ? 'View Final Results' : 'Next Adaptive Question →'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
