/**
 * pages/History.tsx
 * Shows all past exam sessions for the current user.
 * Calls GET /exam-sessions and renders a sortable table with:
 *   date, domain, skill, questions answered, status, and a View Results link.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'

interface ExamSession {
  id: number
  domain: string
  skill: string
  max_questions: number
  questions_answered: number
  status: string
  score?: number
  accuracy?: number
  created_at: string
}

export default function History() {
  const [sessions, setSessions] = useState<ExamSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const res = await client.get('/exam-sessions')
        const data = Array.isArray(res.data) ? res.data : res.data.sessions ?? []
        setSessions(data)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail || 'Failed to load exam history.')
      } finally {
        setLoading(false)
      }
    }
    fetchSessions()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-300 rounded-md">
        <p className="text-red-700">{error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Exam History</h1>
        <Link
          to="/exam/setup"
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          New Exam
        </Link>
      </div>

      {sessions.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <p className="text-gray-500 text-lg font-medium">No exam sessions yet.</p>
          <p className="text-gray-400 text-sm mt-1">
            Start your first exam to see your history here.
          </p>
          <Link
            to="/exam/setup"
            className="inline-block mt-4 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
          >
            Start an Exam
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Date
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Domain
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Skill
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Progress
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Accuracy
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sessions.map((s) => {
                const date = new Date(s.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })
                const accuracyPct =
                  s.accuracy != null ? `${Math.round(s.accuracy * 100)}%` : '-'
                return (
                  <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 text-gray-600">{date}</td>
                    <td className="px-5 py-3 text-gray-800 font-medium">{s.domain}</td>
                    <td className="px-5 py-3 text-gray-600">{s.skill}</td>
                    <td className="px-5 py-3 text-gray-600">
                      {s.questions_answered ?? 0} / {s.max_questions}
                    </td>
                    <td className="px-5 py-3 text-gray-600">{accuracyPct}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="px-5 py-3">
                      {s.status === 'finished' || s.status === 'completed' ? (
                        <Link
                          to={`/exam/results/${s.id}`}
                          className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                          View Results
                        </Link>
                      ) : (
                        <Link
                          to={`/exam/session/${s.id}`}
                          className="text-orange-600 hover:text-orange-800 font-medium"
                        >
                          Resume
                        </Link>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    finished: 'bg-green-100 text-green-700',
    completed: 'bg-green-100 text-green-700',
    active: 'bg-yellow-100 text-yellow-700',
    in_progress: 'bg-yellow-100 text-yellow-700',
    abandoned: 'bg-gray-100 text-gray-500',
  }
  const cls = map[status] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${cls}`}>
      {status?.replace('_', ' ') ?? 'Unknown'}
    </span>
  )
}
