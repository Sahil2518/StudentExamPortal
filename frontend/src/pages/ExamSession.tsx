/**
 * pages/ExamSession.tsx
 * Supports dual exam modes:
 * 1. Live Entrance Exam (JEE / NEET / CAT mode):
 *    - Full Question Palette (jump, Mark for Review, Clear Response)
 *    - Negative marking (+4 / -1)
 *    - No instant feedback / spoilers during exam
 *    - Final submit modal
 *    - Countdown Timer with auto-submit
 * 2. Adaptive Practice Exam:
 *    - Dynamic Thompson Sampling question sequencing
 *    - Immediate feedback & AI tutor explanations
 *
 * Proctoring:
 *    - Fullscreen enforcement (auto re-enter on exit)
 *    - Tab switch / window blur detection → violation counter
 *    - Blocks: right-click, Ctrl+C/V/A/U/S/P, Ctrl+Shift+I/J/C, F12, PrintScreen
 *    - Text selection disabled
 *    - Auto-terminate + submit after 5 violations
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

const MAX_VIOLATIONS = 5

/** Format seconds as MM:SS */
function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

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

  // =========================================================================
  // TIMER STATE
  // =========================================================================
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const timerStartedRef = useRef(false)
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const finishingRef = useRef(false) // prevent double-finish

  // =========================================================================
  // PROCTORING ENFORCEMENT STATE
  // =========================================================================
  const [violations, setViolations] = useState(0)
  const [showViolationWarning, setShowViolationWarning] = useState(false)
  const [violationMessage, setViolationMessage] = useState('')
  const [examTerminated, setExamTerminated] = useState(false)
  const violationsRef = useRef(0) // keep ref in sync for use in closures

  // =========================================================================
  // FINISH SESSION
  // =========================================================================
  const finishSession = useCallback(async () => {
    if (finishingRef.current) return
    finishingRef.current = true
    // Exit fullscreen cleanly
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {})
    }
    setShowSubmitModal(false)
    setPhase('finishing')
    try {
      await client.post(`/exam-sessions/${sessionId}/finish`)
      navigate(`/exam/results/${sessionId}`)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setErrorMsg(axiosErr.response?.data?.detail || 'Failed to finish session.')
      setPhase('error')
      finishingRef.current = false
    }
  }, [sessionId, navigate])

  // =========================================================================
  // VIOLATION HANDLER
  // =========================================================================
  const triggerViolation = useCallback((message: string) => {
    violationsRef.current += 1
    const newCount = violationsRef.current
    setViolations(newCount)
    setViolationMessage(message)
    setShowViolationWarning(true)
    // Report to backend
    sendEvent('proctoring_violation', 'high', 1.0, { message, count: newCount })
    if (newCount >= MAX_VIOLATIONS) {
      setExamTerminated(true)
    }
  }, [sendEvent])

  // =========================================================================
  // AUTO-SUBMIT ON TERMINATION
  // =========================================================================
  useEffect(() => {
    if (examTerminated && session) {
      // Give 3 seconds for the student to see the termination message
      const t = setTimeout(() => {
        finishSession()
      }, 3000)
      return () => clearTimeout(t)
    }
  }, [examTerminated, session, finishSession])

  // =========================================================================
  // TIMER — Initialize once session loads
  // =========================================================================
  useEffect(() => {
    if (!session || phase !== 'question' || timerStartedRef.current) return
    if (!session.time_limit_seconds) return
    timerStartedRef.current = true
    setTimeLeft(session.time_limit_seconds)

    timerIntervalRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev === null) return null
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current!)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
    }
  }, [session, phase])

  // Auto-submit when timer hits 0
  useEffect(() => {
    if (timeLeft === 0 && session && phase === 'question') {
      finishSession()
    }
  }, [timeLeft, session, phase, finishSession])

  // =========================================================================
  // FULLSCREEN ENFORCEMENT
  // =========================================================================
  useEffect(() => {
    if (phase !== 'question' || !session) return

    const enterFullscreen = () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {})
      }
    }

    // Enter fullscreen initially
    enterFullscreen()

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && phase === 'question') {
        triggerViolation('⚠️ Fullscreen mode was exited! This has been recorded.')
        // Attempt to re-enter after a short delay
        setTimeout(enterFullscreen, 1500)
      }
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {})
      }
    }
  }, [phase, session, triggerViolation])

  // =========================================================================
  // PROCTORING — Block shortcuts, right-click, copy, tab-switch
  // =========================================================================
  useEffect(() => {
    if (!session || phase !== 'question') return

    // Block right-click
    const handleContextMenu = (e: MouseEvent) => e.preventDefault()

    // Block copy / cut
    const handleCopy = (e: ClipboardEvent) => {
      e.preventDefault()
      triggerViolation('⚠️ Copy/Cut attempt blocked and recorded.')
    }

    // Block paste
    const handlePaste = (e: ClipboardEvent) => {
      e.preventDefault()
      triggerViolation('⚠️ Paste attempt blocked and recorded.')
    }

    // Block keyboard shortcuts
    const handleKeyDown = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey
      const key = e.key.toLowerCase()

      // PrintScreen
      if (e.key === 'PrintScreen') {
        e.preventDefault()
        triggerViolation('⚠️ Screenshot attempt detected and recorded.')
        return
      }

      // Dev tools & common shortcuts
      if (
        (ctrl && ['c', 'v', 'a', 'u', 's', 'p', 'f'].includes(key)) ||
        (ctrl && e.shiftKey && ['i', 'j', 'c', 'k'].includes(key)) ||
        e.key === 'F12' ||
        e.key === 'F11'
      ) {
        e.preventDefault()
        e.stopPropagation()
        triggerViolation(`⚠️ Blocked shortcut: ${e.ctrlKey ? 'Ctrl+' : ''}${e.shiftKey ? 'Shift+' : ''}${e.key}`)
      }
    }

    // Tab switch / window hidden
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        triggerViolation('⚠️ Tab switch or window minimize detected!')
      }
    }

    // Window blur
    const handleBlur = () => {
      triggerViolation('⚠️ Window lost focus — possible tab switch detected.')
    }

    document.addEventListener('contextmenu', handleContextMenu)
    document.addEventListener('copy', handleCopy)
    document.addEventListener('cut', handleCopy)
    document.addEventListener('paste', handlePaste)
    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('blur', handleBlur)

    return () => {
      document.removeEventListener('contextmenu', handleContextMenu)
      document.removeEventListener('copy', handleCopy)
      document.removeEventListener('cut', handleCopy)
      document.removeEventListener('paste', handlePaste)
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('blur', handleBlur)
    }
  }, [session, phase, triggerViolation])

  // =========================================================================
  // LOAD SESSION
  // =========================================================================
  const loadSession = useCallback(async () => {
    const res = await client.get(`/exam-sessions/${sessionId}`)
    return res.data as SessionDetail
  }, [sessionId])

  const loadPalette = useCallback(async () => {
    const res = await client.get(`/exam-sessions/${sessionId}/live-palette`)
    return res.data.palette as PaletteItem[]
  }, [sessionId])

  const loadLiveQuestion = useCallback(async (seq: number) => {
    const res = await client.get(`/exam-sessions/${sessionId}/question-by-seq/${seq}`)
    const data = res.data as CurrentQuestion
    setLiveQuestion(data)
    setSelectedLiveOption(data.selected_option || null)
    setActiveSeq(seq)
    questionStartRef.current = Date.now()
  }, [sessionId])

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
    let cancelled = false
    const init = async () => {
      setPhase('loading')
      try {
        const s = await loadSession()
        if (cancelled) return
        setSession(s)

        if (s.exam_type === 'live') {
          const pal = await loadPalette()
          if (cancelled) return
          setPalette(pal)
          if (pal.length > 0) {
            await loadLiveQuestion(1)
          }
          if (cancelled) return
          setPhase('question')
        } else {
          const q = await loadNextAdaptiveQuestion(s.id)
          if (cancelled) return
          setAdaptiveQuestion(q)
          questionStartRef.current = Date.now()
          setPhase('question')
        }
      } catch (err: unknown) {
        if (cancelled) return
        const e = err as Error
        setErrorMsg(e.message || 'Failed to initialize session.')
        setPhase('error')
      }
    }
    init()
    return () => { cancelled = true }
  }, [loadSession, loadPalette, loadLiveQuestion, loadNextAdaptiveQuestion])

  // =========================================================================
  // LIVE EXAM HANDLERS
  // =========================================================================
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

      setPalette((prev) =>
        prev.map((item) =>
          item.sequence_number === activeSeq
            ? { ...item, review_status: reviewStatus as PaletteItem['review_status'], selected_option: selectedLiveOption }
            : item
        )
      )

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
    if (targetSeq === activeSeq) return
    if (savingAnswer) {
      let retries = 0
      while (savingAnswer && retries < 15) {
        await new Promise((r) => setTimeout(r, 200))
        retries++
      }
    }
    if (liveQuestion && selectedLiveOption !== liveQuestion.selected_option) {
      await client.post(`/exam-sessions/${sessionId}/live-answer`, {
        question_id: liveQuestion.question_id,
        selected_option: selectedLiveOption,
        review_status: selectedLiveOption ? 'answered' : 'not_answered'
      }).catch(() => {})
    }
    await loadLiveQuestion(targetSeq)
  }

  // =========================================================================
  // ADAPTIVE PRACTICE HANDLERS
  // =========================================================================
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

  // Palette counts
  const answeredCountLive = palette.filter((p) => p.selected_option !== null).length
  const markedReviewCount = palette.filter((p) => p.review_status === 'marked_for_review' || p.review_status === 'answered_and_marked').length
  const notAnsweredCount = palette.length - answeredCountLive

  // =========================================================================
  // SHARED UI HELPERS
  // =========================================================================

  // Timer display color
  const timerColor =
    timeLeft === null
      ? 'text-gray-700'
      : timeLeft < 300
      ? 'text-red-600 font-extrabold animate-pulse'
      : timeLeft < 600
      ? 'text-orange-500 font-bold'
      : 'text-green-700 font-bold'

  // =========================================================================
  // RENDER: ERROR
  // =========================================================================
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
  // RENDER: EXAM TERMINATED
  // =========================================================================
  if (examTerminated) {
    return (
      <div className="fixed inset-0 bg-red-900 flex flex-col items-center justify-center text-white z-50">
        <div className="text-center space-y-4 p-8 max-w-lg">
          <div className="text-6xl">🚫</div>
          <h1 className="text-2xl font-extrabold">Exam Terminated</h1>
          <p className="text-red-200">
            Your exam has been terminated due to <strong>{MAX_VIOLATIONS} proctoring violations</strong>.
            All violations have been recorded and reported.
          </p>
          <div className="bg-red-800 rounded-lg p-4 text-sm text-red-100 text-left space-y-1">
            <p>• Tab switching or window switching</p>
            <p>• Exiting fullscreen mode</p>
            <p>• Attempting to copy content</p>
            <p>• Using blocked keyboard shortcuts</p>
          </div>
          <p className="text-red-300 text-sm animate-pulse">Submitting your exam automatically...</p>
          <Spinner size="md" />
        </div>
      </div>
    )
  }

  // =========================================================================
  // SHARED: VIOLATION WARNING MODAL
  // =========================================================================
  const ViolationModal = () =>
    showViolationWarning ? (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border-2 border-red-500 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">⚠️</span>
            <div>
              <h3 className="text-lg font-extrabold text-red-700">Proctoring Violation Detected</h3>
              <p className="text-xs text-gray-500 mt-0.5">This incident has been recorded</p>
            </div>
          </div>

          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800 font-medium">
            {violationMessage}
          </div>

          <div className="flex justify-between items-center text-sm">
            <span className="text-gray-600">
              Violations: <strong className="text-red-600">{violations}</strong> / {MAX_VIOLATIONS}
            </span>
            {violations >= MAX_VIOLATIONS - 1 && (
              <span className="text-red-700 font-bold text-xs bg-red-50 border border-red-300 px-2 py-1 rounded">
                ⚠️ NEXT VIOLATION = AUTO SUBMIT
              </span>
            )}
          </div>

          {/* Violation progress bar */}
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-red-500 h-2 rounded-full transition-all"
              style={{ width: `${(violations / MAX_VIOLATIONS) * 100}%` }}
            />
          </div>

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
            <strong>Warning:</strong> Any further violations (tab switching, fullscreen exit, copy attempts,
            keyboard shortcuts) will result in automatic exam termination.
          </div>

          <button
            onClick={() => setShowViolationWarning(false)}
            className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white font-bold rounded-lg transition-colors"
          >
            I Understand — Return to Exam
          </button>
        </div>
      </div>
    ) : null

  // =========================================================================
  // 1. LIVE ENTRANCE EXAM UI (JEE / NEET / CAT FORMAT)
  // =========================================================================
  if (session.exam_type === 'live') {
    return (
      // select-none prevents text selection (screenshot prevention)
      <div className="max-w-7xl mx-auto space-y-4 select-none" onContextMenu={(e) => e.preventDefault()}>
        <ViolationModal />

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

          <div className="flex items-center gap-3">
            {/* Violation badge */}
            {violations > 0 && (
              <div className="flex items-center text-xs text-red-700 bg-red-50 px-2.5 py-1 rounded-full border border-red-200">
                ⚠️ Violations: {violations}/{MAX_VIOLATIONS}
              </div>
            )}

            {/* Countdown Timer */}
            {timeLeft !== null && (
              <div className={`flex items-center gap-1.5 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-lg ${timerColor}`}>
                <span className="text-sm">⏱</span>
                <span className="text-base tabular-nums">{formatTime(timeLeft)}</span>
                {timeLeft < 300 && <span className="text-xs">LEFT</span>}
              </div>
            )}

            {/* Webcam + status */}
            <div className="flex items-center text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse mr-1.5" />
              Proctored
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

        {/* Main Grid: Question (Left) & Palette (Right) */}
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

                {/* Options */}
                <div className="space-y-3 pt-2">
                  {Object.entries(liveQuestion.options).map(([key, text]) => {
                    const isSelected = selectedLiveOption === key
                    return (
                      <button
                        type="button"
                        key={key}
                        data-testid={`option-${key}`}
                        onClick={() => setSelectedLiveOption(key)}
                        className={`w-full text-left flex items-start gap-3 p-3.5 rounded-lg border-2 cursor-pointer transition-all ${
                          isSelected
                            ? 'border-indigo-600 bg-indigo-50/60 shadow-sm'
                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold mt-0.5 border shrink-0 ${
                            isSelected
                              ? 'bg-indigo-600 text-white border-indigo-600'
                              : 'bg-white text-gray-600 border-gray-400'
                          }`}
                        >
                          {key}
                        </div>
                        <div className="text-gray-800 text-sm font-normal"><MathText text={text} /></div>
                      </button>
                    )
                  })}
                </div>

                {/* Action Buttons */}
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

            {/* Palette Grid */}
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
                      data-testid={`palette-btn-${item.sequence_number}`}
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

        {/* Submit Confirmation Modal */}
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
                {timeLeft !== null && (
                  <div className="flex justify-between text-gray-600">
                    <span>Time Remaining:</span>
                    <span className={`font-bold ${timeLeft < 300 ? 'text-red-600' : ''}`}>{formatTime(timeLeft)}</span>
                  </div>
                )}
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
    <div className="max-w-3xl mx-auto space-y-6 select-none" onContextMenu={(e) => e.preventDefault()}>
      <ViolationModal />

      {/* Proctoring camera feed */}
      <div className="flex justify-between items-center bg-gray-100 rounded-lg p-3">
        <div className="flex items-center gap-3">
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
          {violations > 0 && (
            <span className="text-xs text-red-600 font-bold bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
              ⚠️ {violations}/{MAX_VIOLATIONS} violations
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {timeLeft !== null && (
            <div className={`flex items-center gap-1.5 bg-white border border-gray-200 px-3 py-1 rounded-lg text-sm tabular-nums ${timerColor}`}>
              ⏱ {formatTime(timeLeft)}
            </div>
          )}
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
                data-testid={`adaptive-option-${key}`}
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
                    <span className={`font-semibold min-w-[1.5rem] ${isCorrect ? 'text-green-600' : isSelected ? 'text-red-500' : 'text-gray-400'}`}>
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

            <div className={`p-4 rounded-md border ${attemptResult.is_correct ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`}>
              <p className={`font-semibold mb-1 ${attemptResult.is_correct ? 'text-green-800' : 'text-red-800'}`}>
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
