/**
 * pages/ReviewerDashboard.tsx
 * Reviewer/admin-only page for reviewing proctoring events.
 * - Loads GET /proctoring-events/flagged-sessions to list flagged exams
 * - Clicking a session loads GET /proctoring-events?exam_session_id=X
 *   and shows a timeline of events (tab-switches, suspicious activity, etc.)
 * - Submit a review decision via POST /review-decisions
 */
import React, { useCallback, useEffect, useState } from 'react'
import client from '../api/client'
import Spinner from '../components/Spinner'

interface FlaggedSession {
  session_id: number
  risk_score: number
  student_name?: string
  student_email?: string
  domain?: string
  skill?: string
  event_count?: number
  created_at?: string
}

interface ProctoringEvent {
  id: number
  event_type: string
  details?: string
  timestamp: string
  severity?: string
}

interface ReviewDecision {
  exam_session_id: number
  decision: 'pass' | 'flag' | 'invalidate'
  notes: string
}

export default function ReviewerDashboard() {
  const [flaggedSessions, setFlaggedSessions] = useState<FlaggedSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Selected session for detail view
  const [selectedSession, setSelectedSession] = useState<FlaggedSession | null>(null)
  const [events, setEvents] = useState<ProctoringEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)

  // Review decision form
  const [decision, setDecision] = useState<'pass' | 'flag' | 'invalidate'>('pass')
  const [notes, setNotes] = useState('')
  const [submittingDecision, setSubmittingDecision] = useState(false)
  const [decisionSuccess, setDecisionSuccess] = useState(false)

  const fetchFlagged = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await client.get('/proctoring-events/flagged-sessions')
      setFlaggedSessions(Array.isArray(res.data) ? res.data : res.data.sessions ?? [])
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Failed to load flagged sessions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchFlagged() }, [fetchFlagged])

  const handleSelectSession = async (session: FlaggedSession) => {
    setSelectedSession(session)
    setEvents([])
    setEventsError(null)
    setDecisionSuccess(false)
    setNotes('')
    setDecision('pass')
    setEventsLoading(true)
    try {
      const res = await client.get('/proctoring-events', {
        params: { exam_session_id: session.session_id },
      })
      setEvents(Array.isArray(res.data) ? res.data : res.data.events ?? [])
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setEventsError(axiosErr.response?.data?.detail || 'Failed to load events.')
    } finally {
      setEventsLoading(false)
    }
  }

  const handleSubmitDecision = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedSession) return
    setSubmittingDecision(true)
    try {
      const payload: ReviewDecision = {
        exam_session_id: selectedSession.session_id,
        decision,
        notes,
      }
      await client.post('/review-decisions', payload)
      setDecisionSuccess(true)
      // Remove from flagged list
      setFlaggedSessions((prev) =>
        prev.filter((s) => s.session_id !== selectedSession.session_id)
      )
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to submit decision.')
    } finally {
      setSubmittingDecision(false)
    }
  }

  // ---- Render ----
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
      <h1 className="text-2xl font-bold text-gray-900">Reviewer Dashboard</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Flagged sessions list */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-base font-semibold text-gray-700">
            Flagged Sessions ({flaggedSessions.length})
          </h2>

          {flaggedSessions.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
              <p className="text-gray-500 text-sm">No flagged sessions to review.</p>
            </div>
          ) : (
            flaggedSessions.map((s) => (
              <button
                key={s.session_id}
                onClick={() => handleSelectSession(s)}
                className={`w-full text-left bg-white rounded-lg border p-4 hover:border-blue-400 transition-colors ${
                  selectedSession?.session_id === s.session_id
                    ? 'border-blue-500 ring-1 ring-blue-500'
                    : 'border-gray-200'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      Session #{s.session_id}
                    </p>
                    {s.student_name && (
                      <p className="text-xs text-gray-500 mt-0.5">{s.student_name}</p>
                    )}
                    {s.domain && (
                      <p className="text-xs text-gray-400 mt-0.5">{s.domain} / {s.skill}</p>
                    )}
                  </div>
                  <RiskBadge score={s.risk_score} />
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                  {s.event_count != null && <span>{s.event_count} events</span>}
                  {s.created_at && (
                    <span>{new Date(s.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Right: Detail panel */}
        <div className="lg:col-span-2">
          {!selectedSession ? (
            <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
              <p className="text-gray-400">Select a session from the left to review.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Session header */}
              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <h3 className="text-lg font-semibold text-gray-900">
                  Session #{selectedSession.session_id}
                </h3>
                <div className="mt-2 flex flex-wrap gap-4 text-sm text-gray-600">
                  {selectedSession.student_name && (
                    <span><strong>Student:</strong> {selectedSession.student_name}</span>
                  )}
                  {selectedSession.student_email && (
                    <span><strong>Email:</strong> {selectedSession.student_email}</span>
                  )}
                  {selectedSession.domain && (
                    <span><strong>Domain:</strong> {selectedSession.domain}</span>
                  )}
                  <span>
                    <strong>Risk Score:</strong>{' '}
                    <span
                      className={`font-bold ${
                        selectedSession.risk_score >= 0.7
                          ? 'text-red-600'
                          : selectedSession.risk_score >= 0.4
                          ? 'text-yellow-600'
                          : 'text-green-600'
                      }`}
                    >
                      {(selectedSession.risk_score * 100).toFixed(0)}%
                    </span>
                  </span>
                </div>
              </div>

              {/* Events timeline */}
              <div className="bg-white rounded-lg border border-gray-200 p-5">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Event Timeline</h4>
                {eventsLoading && <Spinner size="md" />}
                {eventsError && (
                  <p className="text-sm text-red-600">{eventsError}</p>
                )}
                {!eventsLoading && !eventsError && events.length === 0 && (
                  <p className="text-sm text-gray-400">No events recorded for this session.</p>
                )}
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {events.map((ev) => (
                    <div
                      key={ev.id}
                      className={`flex items-start gap-3 p-2 rounded border text-sm ${
                        ev.severity === 'high'
                          ? 'bg-red-50 border-red-200'
                          : ev.severity === 'medium'
                          ? 'bg-yellow-50 border-yellow-200'
                          : 'bg-gray-50 border-gray-200'
                      }`}
                    >
                      <span className="text-xs text-gray-400 whitespace-nowrap mt-0.5">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                      <div>
                        <span className="font-medium text-gray-700">{ev.event_type}</span>
                        {ev.details && (
                          <p className="text-xs text-gray-500 mt-0.5">{ev.details}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Review decision form */}
              {!decisionSuccess ? (
                <div className="bg-white rounded-lg border border-gray-200 p-5">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Submit Decision</h4>
                  <form onSubmit={handleSubmitDecision} className="space-y-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Decision
                      </label>
                      <div className="flex gap-3">
                        {(['pass', 'flag', 'invalidate'] as const).map((d) => (
                          <label key={d} className="flex items-center gap-1.5 cursor-pointer">
                            <input
                              type="radio"
                              name="decision"
                              value={d}
                              checked={decision === d}
                              onChange={() => setDecision(d)}
                              className="accent-blue-600"
                            />
                            <span
                              className={`text-sm font-medium capitalize ${
                                d === 'pass'
                                  ? 'text-green-700'
                                  : d === 'flag'
                                  ? 'text-yellow-700'
                                  : 'text-red-700'
                              }`}
                            >
                              {d}
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Notes
                      </label>
                      <textarea
                        rows={3}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        placeholder="Add reviewer notes..."
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={submittingDecision}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      {submittingDecision && <Spinner size="sm" />}
                      {submittingDecision ? 'Submitting...' : 'Submit Decision'}
                    </button>
                  </form>
                </div>
              ) : (
                <div className="p-4 bg-green-50 border border-green-300 rounded-lg">
                  <p className="text-green-700 font-medium">Decision submitted successfully.</p>
                  <button
                    onClick={() => setSelectedSession(null)}
                    className="mt-2 text-sm text-green-600 underline"
                  >
                    Back to list
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function RiskBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const cls =
    pct >= 70
      ? 'bg-red-100 text-red-700'
      : pct >= 40
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-green-100 text-green-700'
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {pct}% risk
    </span>
  )
}
