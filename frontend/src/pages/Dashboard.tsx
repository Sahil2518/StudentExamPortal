/**
 * pages/Dashboard.tsx
 * Main dashboard shown after login.
 * Fetches:
 *   - GET /performance: overall stats (total attempts, accuracy, etc.)
 *   - GET /knowledge-state: per-skill mastery levels
 * Displays stat cards and a skill mastery summary table.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/Spinner'

interface Performance {
  total_attempts: number
  correct_answers: number
  accuracy: number
  average_time: number
  domains_attempted: string[]
}

interface KnowledgeStateEntry {
  skill: string
  domain: string
  mastery_level: number
  confidence: number
}

export default function Dashboard() {
  const { user } = useAuth()

  const [perf, setPerf] = useState<Performance | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeStateEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const [perfRes, knowledgeRes] = await Promise.all([
          client.get('/performance'),
          client.get('/knowledge-state'),
        ])
        setPerf(perfRes.data)
        // knowledge-state may return an object or array
        const ks = knowledgeRes.data
        setKnowledge(Array.isArray(ks) ? ks : Object.values(ks))
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail || 'Failed to load dashboard data.')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
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

  const accuracy = perf ? Math.round((perf.accuracy ?? 0) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Welcome header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Welcome back, {user?.name}</h1>
          <p className="text-gray-500 mt-1">Here is your performance overview.</p>
        </div>
        <Link
          to="/exam/setup"
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          Start New Exam
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Attempts"
          value={perf?.total_attempts ?? 0}
          sub="questions answered"
        />
        <StatCard
          label="Correct Answers"
          value={perf?.correct_answers ?? 0}
          sub="out of total attempts"
        />
        <StatCard
          label="Accuracy"
          value={`${accuracy}%`}
          sub="overall score rate"
          highlight={accuracy >= 70}
        />
        <StatCard
          label="Avg. Time"
          value={perf?.average_time ? `${Math.round(perf.average_time)}s` : '-'}
          sub="per question"
        />
      </div>

      {/* Domains attempted */}
      {perf?.domains_attempted && perf.domains_attempted.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Domains Attempted</h2>
          <div className="flex flex-wrap gap-2">
            {perf.domains_attempted.map((domain) => (
              <span
                key={domain}
                className="px-3 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-full text-sm"
              >
                {domain}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge state / skill mastery */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Skill Mastery</h2>
        {knowledge.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No skill data yet. Complete an exam to see your mastery levels.
          </p>
        ) : (
          <div className="space-y-3">
            {knowledge.slice(0, 10).map((entry, idx) => {
              const pct = Math.round((entry.mastery_level ?? 0) * 100)
              return (
                <div key={idx}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-gray-700">
                      {entry.skill}
                      {entry.domain && (
                        <span className="ml-2 text-gray-400 text-xs">{entry.domain}</span>
                      )}
                    </span>
                    <span className="text-gray-500">{pct}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-red-400'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <QuickLink to="/exam/setup" title="Take an Exam" desc="Start an adaptive exam session" />
        <QuickLink to="/history" title="View History" desc="Browse past sessions and scores" />
        <QuickLink to="/profile" title="My Profile" desc="View and manage your account" />
      </div>
    </div>
  )
}

/** Small stat display card */
function StatCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string
  value: string | number
  sub: string
  highlight?: boolean
}) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
      <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${highlight ? 'text-green-600' : 'text-gray-900'}`}>
        {value}
      </p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  )
}

/** Dashboard quick-navigation card */
function QuickLink({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="block bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:border-blue-300 hover:shadow transition-all group"
    >
      <h3 className="font-semibold text-gray-800 group-hover:text-blue-600">{title}</h3>
      <p className="text-sm text-gray-500 mt-1">{desc}</p>
    </Link>
  )
}
