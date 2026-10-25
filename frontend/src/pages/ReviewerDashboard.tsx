/**
 * pages/ReviewerDashboard.tsx
 * Human-in-the-Loop Review Pipeline for LLM-generated questions.
 *
 * Displays questions queued for review with full details including
 * correct answers. Reviewers can Approve or Reject each question.
 * Approved questions enter the active question bank; rejected ones are deactivated.
 *
 * Only users with role='reviewer' or role='admin' can access this page.
 */
import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'
import MathText from '../components/MathText'

interface ReviewQuestion {
  id: string
  question_text: string
  domain: string
  skill: string
  difficulty: number
  options: Record<string, string>
  correct_answer: string
  explanation: string
  source: string
  approval_status: string
  created_at?: string
}

type ActionState = 'idle' | 'approving' | 'rejecting' | 'done'

function DifficultyBadge({ level }: { level: number }) {
  const colors = [
    '', 'bg-green-100 text-green-800', 'bg-lime-100 text-lime-800',
    'bg-yellow-100 text-yellow-800', 'bg-orange-100 text-orange-800', 'bg-red-100 text-red-800',
  ]
  const labels = ['', 'Very Easy', 'Easy', 'Medium', 'Hard', 'Very Hard']
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${colors[level] || colors[3]}`}>
      {labels[level] || `Difficulty ${level}`}
    </span>
  )
}

function QuestionCard({
  question: q,
  onCertify,
}: {
  question: ReviewQuestion
  onCertify: (id: string, action: 'approve' | 'reject') => Promise<void>
}) {
  const [actionState, setActionState] = useState<ActionState>('idle')
  const [showExplanation, setShowExplanation] = useState(false)

  const handleAction = async (action: 'approve' | 'reject') => {
    setActionState(action === 'approve' ? 'approving' : 'rejecting')
    try {
      await onCertify(q.id, action)
      setActionState('done')
    } catch {
      setActionState('idle')
    }
  }

  if (actionState === 'done') {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center text-sm text-gray-400 italic">
        ✓ Review submitted
      </div>
    )
  }

  const optionColors: Record<string, string> = {
    A: 'bg-blue-50 border-blue-200',
    B: 'bg-purple-50 border-purple-200',
    C: 'bg-orange-50 border-orange-200',
    D: 'bg-teal-50 border-teal-200',
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      {/* Card Header */}
      <div className="flex items-center justify-between bg-gray-50 px-5 py-3 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-gray-400">{q.id.slice(0, 8)}…</span>
          <span className="text-xs font-semibold text-gray-700 bg-gray-200 px-2 py-0.5 rounded">
            {q.domain}
          </span>
          <span className="text-xs text-gray-500">{q.skill}</span>
          <DifficultyBadge level={q.difficulty} />
        </div>
        <span className="text-xs text-gray-400 italic">via {q.source || 'llm_generated'}</span>
      </div>

      {/* Question Body */}
      <div className="p-5 space-y-4">
        <p className="text-gray-900 text-sm font-medium leading-relaxed">
          <MathText text={q.question_text} />
        </p>

        {/* Options */}
        <div className="grid grid-cols-1 gap-2">
          {Object.entries(q.options).map(([key, text]) => {
            const isCorrect = key === q.correct_answer
            return (
              <div
                key={key}
                className={`flex items-start gap-3 p-2.5 rounded-md border text-xs ${
                  isCorrect
                    ? 'border-green-400 bg-green-50'
                    : optionColors[key] || 'border-gray-200 bg-gray-50'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0 mt-0.5 ${
                    isCorrect ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700'
                  }`}
                >
                  {key}
                </span>
                <span
                  className={`leading-relaxed ${
                    isCorrect ? 'text-green-800 font-semibold' : 'text-gray-700'
                  }`}
                >
                  <MathText text={text} />
                  {isCorrect && (
                    <span className="ml-2 text-green-600 font-bold">✓ Correct Answer</span>
                  )}
                </span>
              </div>
            )
          })}
        </div>

        {/* Explanation toggle */}
        {q.explanation && (
          <div>
            <button
              onClick={() => setShowExplanation(!showExplanation)}
              className="text-xs text-blue-600 hover:underline focus:outline-none"
            >
              {showExplanation ? '▼ Hide Explanation' : '▶ View Explanation'}
            </button>
            {showExplanation && (
              <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-900 leading-relaxed">
                <MathText text={q.explanation} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex justify-end gap-3 px-5 py-3 bg-gray-50 border-t border-gray-200">
        <button
          onClick={() => handleAction('reject')}
          disabled={actionState !== 'idle'}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-bold rounded-md transition-colors"
        >
          {actionState === 'rejecting' ? 'Rejecting…' : '✗ Reject'}
        </button>
        <button
          onClick={() => handleAction('approve')}
          disabled={actionState !== 'idle'}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-bold rounded-md transition-colors"
        >
          {actionState === 'approving' ? 'Approving…' : '✓ Approve'}
        </button>
      </div>
    </div>
  )
}

export default function ReviewerDashboard() {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState<ReviewQuestion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [domainFilter, setDomainFilter] = useState('')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const fetchPending = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (domainFilter.trim()) params.domain = domainFilter.trim()
      const res = await client.get('/questions/pending-review', { params })
      setQuestions(res.data)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } }
      if (axiosErr.response?.status === 403) {
        setError('Access denied. Only reviewers and admins can access this dashboard.')
      } else {
        setError(axiosErr.response?.data?.detail || 'Failed to load review queue.')
      }
    } finally {
      setLoading(false)
    }
  }, [domainFilter])

  useEffect(() => {
    fetchPending()
  }, [fetchPending])

  const handleCertify = async (questionId: string, action: 'approve' | 'reject') => {
    await client.post(`/questions/${questionId}/certify`, { action })
    setSuccessMessage(`Question ${action === 'approve' ? 'approved ✓' : 'rejected ✗'}`)
    setTimeout(() => setSuccessMessage(null), 3000)
    // Remove the certified question from local list immediately
    setQuestions((prev) => prev.filter((q) => q.id !== questionId))
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🔍 Question Review Queue</h1>
          <p className="text-xs text-gray-500 mt-1">
            Human-in-the-Loop pipeline — verify AI-generated questions before they enter the student question bank
          </p>
        </div>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-4 py-2 border border-gray-300 text-gray-600 text-xs font-medium rounded-md hover:bg-gray-50 transition-colors"
        >
          ← Dashboard
        </button>
      </div>

      {/* Success Toast */}
      {successMessage && (
        <div className="bg-green-50 border border-green-300 rounded-md px-4 py-3 text-sm text-green-800 font-medium">
          {successMessage}
        </div>
      )}

      {/* Filters & Stats Bar */}
      <div className="flex items-center gap-4 bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
        <div className="flex items-center gap-2 flex-1">
          <label className="text-xs text-gray-600 font-medium whitespace-nowrap">
            Filter by domain:
          </label>
          <input
            type="text"
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            placeholder="e.g. Physics, Mathematics…"
            className="flex-1 text-xs border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <button
            onClick={fetchPending}
            className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-md hover:bg-indigo-700 transition-colors"
          >
            Apply
          </button>
        </div>
        <div className="text-xs text-gray-500 whitespace-nowrap">
          <span className="font-bold text-indigo-700">{questions.length}</span> pending
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center items-center h-48">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-300 rounded-lg p-5 text-sm text-red-700">
          {error}
        </div>
      ) : questions.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
          <div className="text-4xl mb-3">🎉</div>
          <p className="text-gray-700 font-medium">Review queue is empty!</p>
          <p className="text-xs text-gray-400 mt-1">All generated questions have been reviewed.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {questions.map((q) => (
            <QuestionCard key={q.id} question={q} onCertify={handleCertify} />
          ))}
        </div>
      )}
    </div>
  )
}
