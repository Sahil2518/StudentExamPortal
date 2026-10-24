/**
 * pages/AdminDashboard.tsx
 * Admin-only page with two tabs:
 *   1. Users - lists all users (GET /admin/users) with role-change dropdowns
 *   2. Questions - lists all questions (GET /questions), approve/deactivate,
 *      and an "Add Question" form (POST /questions)
 * Access is restricted by ProtectedRoute (requireAdmin).
 */
import React, { useCallback, useEffect, useState } from 'react'
import client from '../api/client'
import Spinner from '../components/Spinner'

type Tab = 'users' | 'questions'

// ---- Types ----
interface AdminUser {
  id: number
  name: string
  email: string
  role: string
  created_at: string
}

interface Question {
  id: number
  question_text: string
  domain: string
  skill: string
  difficulty: number
  correct_answer: string
  is_active: boolean
  is_approved: boolean
}

interface NewQuestion {
  question_text: string
  domain: string
  skill: string
  difficulty: number
  options: Record<string, string>
  correct_answer: string
  explanation: string
}

const ROLES = ['student', 'reviewer', 'admin']

// =========================================================
export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('users')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>

      {/* Tab bar */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-6">
          {(['users', 'questions'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 capitalize transition-colors ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'questions' && <QuestionsTab />}
    </div>
  )
}

// =========================================================
// USERS TAB
// =========================================================
function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [changingRole, setChangingRole] = useState<number | null>(null)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await client.get('/admin/users')
      setUsers(Array.isArray(res.data) ? res.data : res.data.users ?? [])
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Failed to load users.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleRoleChange = async (userId: number, newRole: string) => {
    setChangingRole(userId)
    try {
      await client.patch(`/admin/users/${userId}/role`, { role: newRole })
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      )
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to update role.')
    } finally {
      setChangingRole(null)
    }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>
  if (error) return <div className="p-4 bg-red-50 border border-red-300 rounded-md text-red-700">{error}</div>

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {['ID', 'Name', 'Email', 'Role', 'Joined', 'Change Role'].map((h) => (
              <th key={h} className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-gray-50">
              <td className="px-5 py-3 text-gray-500">{u.id}</td>
              <td className="px-5 py-3 font-medium text-gray-900">{u.name}</td>
              <td className="px-5 py-3 text-gray-600">{u.email}</td>
              <td className="px-5 py-3">
                <RoleBadge role={u.role} />
              </td>
              <td className="px-5 py-3 text-gray-500">
                {new Date(u.created_at).toLocaleDateString()}
              </td>
              <td className="px-5 py-3">
                <div className="flex items-center gap-2">
                  <select
                    defaultValue={u.role}
                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    disabled={changingRole === u.id}
                    className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  {changingRole === u.id && <Spinner size="sm" />}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// =========================================================
// QUESTIONS TAB
// =========================================================
function QuestionsTab() {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionId, setActionId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)

  const fetchQuestions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await client.get('/questions')
      setQuestions(Array.isArray(res.data) ? res.data : res.data.questions ?? [])
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Failed to load questions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchQuestions() }, [fetchQuestions])

  const handleApprove = async (id: number) => {
    setActionId(id)
    try {
      await client.patch(`/questions/${id}/approve`)
      setQuestions((prev) => prev.map((q) => q.id === id ? { ...q, is_approved: true } : q))
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to approve.')
    } finally {
      setActionId(null)
    }
  }

  const handleDeactivate = async (id: number) => {
    setActionId(id)
    try {
      await client.patch(`/questions/${id}/deactivate`)
      setQuestions((prev) => prev.map((q) => q.id === id ? { ...q, is_active: false } : q))
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to deactivate.')
    } finally {
      setActionId(null)
    }
  }

  const filtered = questions.filter(
    (q) =>
      q.question_text?.toLowerCase().includes(search.toLowerCase()) ||
      q.domain?.toLowerCase().includes(search.toLowerCase()) ||
      q.skill?.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>
  if (error) return <div className="p-4 bg-red-50 border border-red-300 rounded-md text-red-700">{error}</div>

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search questions, domains, skills..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={() => setShowForm((p) => !p)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
        >
          {showForm ? 'Hide Form' : 'Add Question'}
        </button>
      </div>

      {/* Add Question form */}
      {showForm && <AddQuestionForm onSuccess={() => { setShowForm(false); fetchQuestions() }} />}

      {/* Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['ID', 'Question', 'Domain', 'Skill', 'Difficulty', 'Status', 'Actions'].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No questions found.
                </td>
              </tr>
            ) : (
              filtered.map((q) => (
                <tr key={q.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500">{q.id}</td>
                  <td className="px-4 py-3 text-gray-800 max-w-xs">
                    <span title={q.question_text}>
                      {q.question_text?.length > 60
                        ? `${q.question_text.slice(0, 60)}...`
                        : q.question_text}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{q.domain}</td>
                  <td className="px-4 py-3 text-gray-600">{q.skill}</td>
                  <td className="px-4 py-3 text-gray-600">{q.difficulty?.toFixed(1) ?? '-'}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {q.is_approved && (
                        <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs">Approved</span>
                      )}
                      {!q.is_active && (
                        <span className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">Inactive</span>
                      )}
                      {!q.is_approved && q.is_active && (
                        <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">Pending</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {!q.is_approved && (
                        <button
                          onClick={() => handleApprove(q.id)}
                          disabled={actionId === q.id}
                          className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          {actionId === q.id && <Spinner size="sm" />}
                          Approve
                        </button>
                      )}
                      {q.is_active && (
                        <button
                          onClick={() => handleDeactivate(q.id)}
                          disabled={actionId === q.id}
                          className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          {actionId === q.id && <Spinner size="sm" />}
                          Deactivate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// =========================================================
// ADD QUESTION FORM
// =========================================================
function AddQuestionForm({ onSuccess }: { onSuccess: () => void }) {
  const empty: NewQuestion = {
    question_text: '',
    domain: '',
    skill: '',
    difficulty: 0.5,
    options: { A: '', B: '', C: '', D: '' },
    correct_answer: 'A',
    explanation: '',
  }
  const [form, setForm] = useState<NewQuestion>(empty)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    // Validate all options filled
    if (Object.values(form.options).some((v) => !v.trim())) {
      setError('All four answer options (A-D) are required.')
      return
    }
    setSubmitting(true)
    try {
      await client.post('/questions', form)
      setForm(empty)
      onSuccess()
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Failed to create question.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 space-y-4">
      <h3 className="text-base font-semibold text-gray-800">Add New Question</h3>

      {error && (
        <div className="p-3 bg-red-50 border border-red-300 rounded text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Domain *</label>
            <input
              required
              value={form.domain}
              onChange={(e) => setForm((p) => ({ ...p, domain: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Skill *</label>
            <input
              required
              value={form.skill}
              onChange={(e) => setForm((p) => ({ ...p, skill: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Difficulty: <strong>{form.difficulty}</strong>
            </label>
            <input
              type="range" min={0.1} max={1.0} step={0.1}
              value={form.difficulty}
              onChange={(e) => setForm((p) => ({ ...p, difficulty: parseFloat(e.target.value) }))}
              className="w-full accent-blue-600"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Question Text *</label>
          <textarea
            required
            rows={3}
            value={form.question_text}
            onChange={(e) => setForm((p) => ({ ...p, question_text: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Options A-D */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {(['A', 'B', 'C', 'D'] as const).map((key) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">Option {key} *</label>
              <input
                required
                value={form.options[key]}
                onChange={(e) =>
                  setForm((p) => ({ ...p, options: { ...p.options, [key]: e.target.value } }))
                }
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Correct Answer *</label>
            <select
              value={form.correct_answer}
              onChange={(e) => setForm((p) => ({ ...p, correct_answer: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {['A', 'B', 'C', 'D'].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Explanation</label>
            <input
              value={form.explanation}
              onChange={(e) => setForm((p) => ({ ...p, explanation: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {submitting && <Spinner size="sm" />}
            {submitting ? 'Saving...' : 'Save Question'}
          </button>
        </div>
      </form>
    </div>
  )
}

function RoleBadge({ role }: { role: string }) {
  const colors: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-700',
    reviewer: 'bg-orange-100 text-orange-700',
    student: 'bg-blue-100 text-blue-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${colors[role] ?? 'bg-gray-100 text-gray-600'}`}>
      {role}
    </span>
  )
}
