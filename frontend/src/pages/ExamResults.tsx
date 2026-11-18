/**
 * pages/ExamResults.tsx
 * Results page shown after an exam session finishes.
 * Displays:
 * 1. Live Entrance Scorecard (Raw Score, Negative Deductions, Attempted vs Unattempted)
 * 2. Accuracy & Question Breakdown
 * 3. Topic Skill Breakdown & Recommendations
 */
import React, { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import client from '../api/client'
import Spinner from '../components/Spinner'
import MathText from '../components/MathText'

interface RapidGuessFlag {
  question_id: string
  skill: string
  difficulty: number
  time_taken_seconds: number
  threshold_seconds: number
  was_correct: boolean
}

interface FatigueBucket {
  segment: string
  questions: number
  attempted: number
  correct: number
  accuracy_pct: number
  avg_time_seconds: number | null
}

interface FatigueAnalytics {
  rapid_guess_count: number
  rapid_guess_flags: RapidGuessFlag[]
  fatigue_detected: boolean
  fatigue_severity: string
  fatigue_buckets: FatigueBucket[]
  total_exam_time_seconds: number | null
}

interface ThetaVector {
  theta_conceptual: number
  theta_numerical: number
  theta_analytical: number
  composite_theta: number
  n_conceptual: number
  n_numerical: number
  n_analytical: number
}

interface QuestionResult {
  question_id: string
  question_text: string
  selected_answer: string
  correct_answer: string
  is_correct: boolean
  explanation: string
  skill: string
}

interface SkillStat {
  skill: string
  accuracy: number
}

interface Scorecard {
  raw_score: number
  positive_marks_earned: number
  negative_marks_deducted: number
  max_possible_marks: number
  correct_count: number
  incorrect_count: number
  unattempted_count: number
  total_questions: number
}

interface ProctoringIncident {
  event_type: string
  severity: string
  confidence: number
  occurred_at: string | null
  metadata?: Record<string, unknown>
}

interface ProctoringSummary {
  integrity_status: 'VERIFIED_CLEAN' | 'MONITORED_WITH_INFRACTIONS' | 'FLAGGED_FOR_REVIEW'
  integrity_badge: string
  total_violations: number
  risk_score: number
  flagged_for_review: boolean
  violation_counts: Record<string, number>
  incident_log: ProctoringIncident[]
}

interface ResultsData {
  id: string
  domain: string
  skill?: string
  total_questions: number
  correct_count: number
  accuracy: number
  exam_type?: string
  exam_paper_title?: string
  raw_score?: number
  positive_mark?: number
  negative_mark?: number
  scorecard?: Scorecard
  question_results: QuestionResult[]
  skill_breakdown?: SkillStat[]
  recommendations: Array<string | { skill?: string; suggestion?: string; priority?: number; [key: string]: unknown }>
  fatigue_analytics?: FatigueAnalytics
  theta_vector?: ThetaVector
  proctoring_summary?: ProctoringSummary
}

export default function ExamResults() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<ResultsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showIncidentLog, setShowIncidentLog] = useState(false)

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const res = await client.get(`/exam-sessions/${sessionId}/results`)
        setData(res.data)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail || 'Failed to load results.')
      } finally {
        setLoading(false)
      }
    }
    fetchResults()
  }, [sessionId])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-4 bg-red-50 border border-red-300 rounded-md max-w-2xl mx-auto mt-8">
        <p className="text-red-700">{error || 'No results found.'}</p>
        <button
          onClick={() => navigate('/history')}
          className="mt-3 px-4 py-2 bg-gray-600 text-white rounded-md text-sm"
        >
          Back to History
        </button>
      </div>
    )
  }

  const accuracyPct = Math.round((data.accuracy ?? 0) * 100)
  const chartData =
    data.skill_breakdown?.map((s) => ({
      skill: s.skill,
      accuracy: Math.round((s.accuracy ?? 0) * 100),
    })) ?? []

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {data.exam_paper_title || 'Examination Results'}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            {data.exam_type === 'live' ? '🏛️ Standardized Entrance Paper' : '🧠 Adaptive Practice Session'} • {data.domain}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate('/exam/setup')}
            className="px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-md hover:bg-indigo-700 transition-colors shadow"
          >
            Take Another Exam
          </button>
          <button
            onClick={() => navigate('/history')}
            className="px-4 py-2 border border-gray-300 text-gray-700 text-xs font-medium rounded-md hover:bg-gray-50 transition-colors"
          >
            View History
          </button>
        </div>
      </div>

      {/* Official Entrance Scorecard Banner */}
      {data.scorecard && (
        <div className="bg-gradient-to-r from-indigo-900 to-indigo-700 rounded-lg p-6 text-white shadow-lg space-y-4">
          <div className="flex flex-wrap justify-between items-center gap-2 border-b border-indigo-600/60 pb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-indigo-200">
              {data.exam_paper_title ? `Scorecard • ${data.exam_paper_title}` : 'Official Entrance Scorecard'}
            </span>
            <span className="text-xs bg-indigo-500/40 text-indigo-100 px-2 py-0.5 rounded font-mono">
              Marking Scheme: +{data.positive_mark || 4} / -{data.negative_mark || 1}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-indigo-200">Net Score</div>
              <div className="text-2xl font-extrabold text-white mt-1">
                {data.scorecard.raw_score > 0 ? `+${data.scorecard.raw_score}` : data.scorecard.raw_score}
                <span className="text-xs font-normal text-indigo-200 ml-1">/ {data.scorecard.max_possible_marks}</span>
              </div>
            </div>

            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-green-300">Marks Earned</div>
              <div className="text-xl font-bold text-green-400 mt-1">
                +{data.scorecard.positive_marks_earned}
                <span className="text-xs font-normal text-indigo-200 ml-1">({data.scorecard.correct_count} correct)</span>
              </div>
            </div>

            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-red-300">Negative Penalty</div>
              <div className="text-xl font-bold text-red-400 mt-1">
                -{data.scorecard.negative_marks_deducted}
                <span className="text-xs font-normal text-indigo-200 ml-1">({data.scorecard.incorrect_count} wrong)</span>
              </div>
            </div>

            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-indigo-200">Unattempted</div>
              <div className="text-xl font-bold text-white mt-1">
                {data.scorecard.unattempted_count}
                <span className="text-xs font-normal text-indigo-200 ml-1">questions</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <SummaryCard label="Domain" value={data.domain} />
        <SummaryCard label="Total Questions" value={data.total_questions || data.question_results.length} />
        <SummaryCard label="Correct Answers" value={data.correct_count} />
        <SummaryCard
          label="Accuracy"
          value={`${accuracyPct}%`}
          highlight={accuracyPct >= 70}
        />
      </div>

      {/* Skill Breakdown Chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
          <h2 className="text-sm font-bold text-gray-800 mb-4">Topic Skill Performance</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="skill" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar dataKey="accuracy" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.accuracy >= 70 ? '#22c55e' : entry.accuracy >= 40 ? '#f59e0b' : '#ef4444'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations && data.recommendations.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-2">
          <h2 className="text-xs font-bold text-blue-900 uppercase tracking-wide">
            💡 AI Study Recommendations
          </h2>
          <ul className="space-y-1">
            {data.recommendations.map((rec, i) => {
              let text = ''
              if (typeof rec === 'string') {
                text = rec
              } else if (rec && typeof rec === 'object') {
                const recObj = rec as { skill?: string; suggestion?: string }
                text = recObj.suggestion
                  ? (recObj.skill ? `[${recObj.skill}] ${recObj.suggestion}` : recObj.suggestion)
                  : JSON.stringify(rec)
              }
              return (
                <li key={i} className="text-xs text-blue-800 flex items-start gap-2">
                  <span className="text-blue-500 mt-0.5">•</span>
                  <span>{text}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* MIRT: 3D Ability Vector */}
      {data.theta_vector && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-3">
          <h2 className="text-sm font-bold text-gray-800">🧬 Multidimensional Ability Profile (MIRT)</h2>
          <p className="text-xs text-gray-500">
            Your cognitive ability estimated across 3 independent dimensions using Item Response Theory.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { key: 'theta_conceptual', label: 'Conceptual', icon: '📚', n: data.theta_vector.n_conceptual },
              { key: 'theta_numerical', label: 'Numerical', icon: '🔢', n: data.theta_vector.n_numerical },
              { key: 'theta_analytical', label: 'Analytical', icon: '🔍', n: data.theta_vector.n_analytical },
            ].map(({ key, label, icon, n }) => {
              const raw = data.theta_vector![key as keyof ThetaVector] as number
              const pct = Math.round(((raw + 4) / 8) * 100)
              const color = raw >= 1 ? 'bg-green-500' : raw >= -0.5 ? 'bg-yellow-400' : 'bg-red-400'
              return (
                <div key={key} className="bg-gray-50 rounded-lg border border-gray-200 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-700">{icon} {label}</span>
                    <span className="text-xs text-gray-400">{n}q</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="text-center">
                    <span className={`text-lg font-bold ${raw >= 1 ? 'text-green-700' : raw >= -0.5 ? 'text-yellow-600' : 'text-red-600'}`}>
                      {raw >= 0 ? '+' : ''}{raw.toFixed(2)}
                    </span>
                    <span className="text-xs text-gray-400 ml-1">θ</span>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="bg-indigo-50 border border-indigo-200 rounded-md px-4 py-2 flex items-center justify-between">
            <span className="text-xs text-indigo-700 font-medium">Composite Ability (θ)</span>
            <span className="text-base font-extrabold text-indigo-800">
              {data.theta_vector.composite_theta >= 0 ? '+' : ''}{data.theta_vector.composite_theta.toFixed(2)}
            </span>
          </div>
        </div>
      )}

      {/* Cognitive Fatigue Analytics */}
      {data.fatigue_analytics && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-800">🧠 Cognitive Fatigue Analytics</h2>
            {data.fatigue_analytics.fatigue_detected && (
              <span className={`text-xs font-bold px-2 py-1 rounded ${
                data.fatigue_analytics.fatigue_severity === 'severe'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-yellow-100 text-yellow-700'
              }`}>
                ⚠ {data.fatigue_analytics.fatigue_severity.charAt(0).toUpperCase() + data.fatigue_analytics.fatigue_severity.slice(1)} Fatigue Detected
              </span>
            )}
            {!data.fatigue_analytics.fatigue_detected && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-green-100 text-green-700">
                ✓ No Fatigue Detected
              </span>
            )}
          </div>

          {/* Fatigue Curve Buckets */}
          {data.fatigue_analytics.fatigue_buckets.length > 0 && (
            <div className="grid grid-cols-3 gap-3">
              {data.fatigue_analytics.fatigue_buckets.map((bucket, i) => (
                <div key={i} className="bg-gray-50 rounded-lg border border-gray-200 p-3 space-y-1">
                  <div className="text-xs font-semibold text-gray-600">{bucket.segment}</div>
                  <div className="text-lg font-bold text-gray-900">{bucket.accuracy_pct}%</div>
                  <div className="text-xs text-gray-400">accuracy</div>
                  {bucket.avg_time_seconds != null && (
                    <div className="text-xs text-gray-500">{bucket.avg_time_seconds}s avg/q</div>
                  )}
                  <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                    <div
                      className={`h-1.5 rounded-full ${bucket.accuracy_pct >= 70 ? 'bg-green-500' : bucket.accuracy_pct >= 40 ? 'bg-yellow-400' : 'bg-red-400'}`}
                      style={{ width: `${bucket.accuracy_pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Rapid Guess Flags */}
          {data.fatigue_analytics.rapid_guess_count > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-orange-700">⚡ Rapid Guesses Detected:</span>
                <span className="text-xs font-bold bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                  {data.fatigue_analytics.rapid_guess_count} questions
                </span>
              </div>
              <div className="space-y-1">
                {data.fatigue_analytics.rapid_guess_flags.map((flag, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs bg-orange-50 border border-orange-200 rounded px-3 py-1.5">
                    <span className="text-orange-600 font-mono">{flag.time_taken_seconds}s</span>
                    <span className="text-gray-600">{flag.skill || 'Unknown Topic'}</span>
                    <span className="text-gray-400">Difficulty: {flag.difficulty}/5</span>
                    <span className={`ml-auto font-semibold ${flag.was_correct ? 'text-green-600' : 'text-red-500'}`}>
                      {flag.was_correct ? '✓ Correct' : '✗ Wrong'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.fatigue_analytics.total_exam_time_seconds != null && (
            <div className="text-xs text-gray-500 text-right">
              Total tracked time: <strong>{Math.round(data.fatigue_analytics.total_exam_time_seconds / 60)} min {data.fatigue_analytics.total_exam_time_seconds % 60}s</strong>
            </div>
          )}
        </div>
      )}

      {/* Academic Integrity & Proctoring Forensic Audit */}
      {data.proctoring_summary && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">🛡️</span>
              <div>
                <h2 className="text-sm font-bold text-gray-900">Academic Integrity & Proctoring Audit</h2>
                <p className="text-xs text-gray-500">Edge WebGL Neural Proctoring • Cryptographic Audit Trail</p>
              </div>
            </div>
            <span
              className={`text-xs font-bold px-3 py-1 rounded-full border ${
                data.proctoring_summary.integrity_status === 'VERIFIED_CLEAN'
                  ? 'bg-green-50 border-green-300 text-green-700'
                  : data.proctoring_summary.integrity_status === 'MONITORED_WITH_INFRACTIONS'
                  ? 'bg-amber-50 border-amber-300 text-amber-700'
                  : 'bg-red-50 border-red-300 text-red-700'
              }`}
            >
              {data.proctoring_summary.integrity_badge}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <div className="text-xs text-gray-500">Integrity Risk Score</div>
              <div
                className={`text-lg font-bold mt-0.5 ${
                  data.proctoring_summary.risk_score < 0.2
                    ? 'text-green-600'
                    : data.proctoring_summary.risk_score < 0.5
                    ? 'text-amber-600'
                    : 'text-red-600'
                }`}
              >
                {(data.proctoring_summary.risk_score * 100).toFixed(1)}%
              </div>
              <div className="text-[10px] text-gray-400">0.0% is optimal</div>
            </div>

            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <div className="text-xs text-gray-500">Logged Infractions</div>
              <div className="text-lg font-bold text-gray-800 mt-0.5">
                {data.proctoring_summary.total_violations} <span className="text-xs font-normal text-gray-500">/ 5 max</span>
              </div>
              <div className="text-[10px] text-gray-400">Threshold: 5 auto-submit</div>
            </div>

            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <div className="text-xs text-gray-500">Human Review Status</div>
              <div className="text-sm font-semibold text-gray-800 mt-1">
                {data.proctoring_summary.flagged_for_review ? (
                  <span className="text-red-600">Pending Review</span>
                ) : (
                  <span className="text-green-600">No Action Required</span>
                )}
              </div>
              <div className="text-[10px] text-gray-400">Institutional Audit</div>
            </div>

            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <div className="text-xs text-gray-500">AI Computer Vision</div>
              <div className="text-sm font-semibold text-indigo-700 mt-1">
                TinyFace WebGL
              </div>
              <div className="text-[10px] text-gray-400">Client-Side Edge Inference</div>
            </div>
          </div>

          {data.proctoring_summary.total_violations === 0 ? (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-3">
              <span className="text-green-600 text-lg">✓</span>
              <p className="text-xs text-green-800">
                <strong>Flawless Session Integrity:</strong> No tab switches, window un-focusing, or facial occlusions detected throughout this exam session.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-gray-600">Infraction Breakdown:</span>
                {Object.entries(data.proctoring_summary.violation_counts).map(([type, count]) => (
                  <span
                    key={type}
                    className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded font-mono font-medium"
                  >
                    {type.replace(/_/g, ' ')}: {count}
                  </span>
                ))}
              </div>

              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowIncidentLog((prev) => !prev)}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                >
                  {showIncidentLog ? 'Hide Incident Timestamp Log ▲' : `View Incident Forensic Timeline (${data.proctoring_summary.incident_log.length} events) ▼`}
                </button>

                {showIncidentLog && (
                  <div className="mt-2 overflow-x-auto border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
                    <table className="min-w-full text-xs divide-y divide-gray-200">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">Timestamp</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">Event Type</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">Severity</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">Confidence</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 bg-white">
                        {data.proctoring_summary.incident_log.map((inc, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-3 py-1.5 text-gray-600 font-mono">
                              {inc.occurred_at ? new Date(inc.occurred_at).toLocaleTimeString() : 'N/A'}
                            </td>
                            <td className="px-3 py-1.5 text-gray-800 font-medium">
                              {inc.event_type.replace(/_/g, ' ')}
                            </td>
                            <td className="px-3 py-1.5">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                  inc.severity === 'high'
                                    ? 'bg-red-100 text-red-700'
                                    : inc.severity === 'medium'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-gray-100 text-gray-600'
                                }`}
                              >
                                {inc.severity}
                              </span>
                            </td>
                            <td className="px-3 py-1.5 text-gray-500 font-mono">
                              {(inc.confidence * 100).toFixed(0)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detailed Per-Question Breakdown */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 space-y-4">        <h2 className="text-sm font-bold text-gray-900">Per-Question Review & Solutions</h2>
        <div className="space-y-4">
          {data.question_results.map((q, idx) => (
            <div
              key={q.question_id || idx}
              className={`p-4 rounded-lg border text-xs space-y-2 ${
                q.is_correct ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-red-50/30'
              }`}
            >
              <div className="flex justify-between items-center font-bold">
                <span className="text-gray-800">Question {idx + 1}</span>
                <span className={q.is_correct ? 'text-green-700' : 'text-red-600'}>
                  {q.is_correct ? '✓ Correct (+4)' : '✗ Incorrect (-1)'}
                </span>
              </div>
              <p className="text-gray-800 text-sm font-medium"><MathText text={q.question_text} /></p>
              <div className="flex gap-4 text-xs">
                <span>
                  Your Answer:{' '}
                  <strong className={q.is_correct ? 'text-green-700' : 'text-red-600'}>
                    {q.selected_answer || 'Unattempted'}
                  </strong>
                </span>
                <span>
                  Correct Answer: <strong className="text-green-700">{q.correct_answer}</strong>
                </span>
              </div>
              {q.explanation && (
                <div className="bg-white p-2.5 rounded border border-gray-200 text-gray-700 mt-2">
                  <span className="font-semibold text-gray-900">Solution: </span>
                  <MathText text={q.explanation} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function SummaryCard({
  label,
  value,
  highlight = false,
}: {
  label: string
  value: string | number
  highlight?: boolean
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="text-xs text-gray-500 font-medium">{label}</div>
      <div className={`text-xl font-bold mt-1 ${highlight ? 'text-green-600' : 'text-gray-800'}`}>
        {value}
      </div>
    </div>
  )
}
