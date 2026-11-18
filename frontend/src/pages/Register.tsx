/**
 * pages/Register.tsx
 * Modern, high-conversion candidate registration interface.
 * Features:
 * - Real-time password strength meter
 * - Password confirmation validation
 * - Show/Hide password toggles
 * - Seamless automatic sign-in upon account creation
 */
import React, { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/Spinner'

export default function Register() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Password Strength Calculation (0 to 4)
  const passwordStrength = useMemo(() => {
    if (!password) return 0
    let score = 0
    if (password.length >= 6) score += 1
    if (password.length >= 10) score += 1
    if (/[0-9]/.test(password)) score += 1
    if (/[^A-Za-z0-9]/.test(password) || (/[A-Z]/.test(password) && /[a-z]/.test(password))) score += 1
    return score
  }, [password])

  const strengthLabels = ['', 'Weak', 'Fair', 'Good', 'Strong']
  const strengthColors = ['', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500']

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const cleanName = name.trim()
    const cleanEmail = email.trim().toLowerCase()

    if (!cleanName || !cleanEmail || !password) {
      setError('Please fill out all required fields.')
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please verify and re-enter.')
      return
    }

    setLoading(true)
    try {
      // 1. Create account
      await client.post('/register', {
        name: cleanName,
        email: cleanEmail,
        password,
      })

      // 2. Seamless modern auto-login
      try {
        await login(cleanEmail, password)
        navigate('/dashboard', { replace: true })
      } catch {
        // Fallback: redirect to login if auto-login token fetch fails
        navigate('/login', { state: { registered: true } })
      }
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { status?: number; data?: { detail?: string | Array<{ msg: string }> } }
        code?: string
      }

      if (!axiosErr.response) {
        if (axiosErr.code === 'ECONNABORTED') {
          setError('Server took too long to respond. The cloud service may be waking up. Please try again.')
        } else if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          setError('Cannot connect to backend server. Please verify start_server.bat is running.')
        } else {
          setError('Cannot connect to backend server. The cloud service may be waking up (can take 30-50s). Please try again.')
        }
      } else {
        const status = axiosErr.response.status
        const detail = axiosErr.response.data?.detail

        if (typeof detail === 'string') {
          setError(detail)
        } else if (Array.isArray(detail) && detail.length > 0) {
          setError(detail.map((d) => d.msg).join(', '))
        } else if (status === 400) {
          setError('An account with this email address already exists or the details are invalid. Please check and try again.')
        } else {
          setError('Registration failed. Please check your details and try again.')
        }
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      {/* Brand Header */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-500/30 mb-4 text-2xl font-black">
          🏛️
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          Create Candidate Account
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Register to access standardized entrance mocks and diagnostic tests
        </p>
      </div>

      {/* Auth Card */}
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-100 sm:px-10">
          {/* Error Banner */}
          {error && (
            <div className="mb-5 p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-800 animate-in fade-in duration-200">
              <span className="text-base text-red-600">⚠️</span>
              <span className="font-medium pt-0.5">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Full Name */}
            <div>
              <label htmlFor="name" className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Sahil Agarwal"
                className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="student@example.com"
                className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400"
              />
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                  Password
                </label>
                {password && (
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${
                    passwordStrength <= 1 ? 'text-red-500' : passwordStrength === 2 ? 'text-amber-500' : 'text-emerald-600'
                  }`}>
                    {strengthLabels[passwordStrength]}
                  </span>
                )}
              </div>

              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  className="w-full px-3.5 py-2.5 pr-10 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-medium px-1"
                  tabIndex={-1}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>

              {/* Password strength bar */}
              {password && (
                <div className="mt-1.5 flex gap-1 h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                  {[1, 2, 3, 4].map((step) => (
                    <div
                      key={step}
                      className={`flex-1 transition-all duration-300 ${
                        passwordStrength >= step ? strengthColors[passwordStrength] : 'bg-transparent'
                      }`}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="confirmPassword" className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                  Confirm Password
                </label>
                {confirmPassword && (
                  <span className={`text-[10px] font-bold ${
                    password === confirmPassword ? 'text-emerald-600' : 'text-red-500'
                  }`}>
                    {password === confirmPassword ? '✓ Passwords match' : '✕ Must match'}
                  </span>
                )}
              </div>
              <input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                className={`w-full px-3.5 py-2.5 text-sm bg-slate-50 border rounded-xl focus:bg-white focus:outline-none focus:ring-2 transition-all placeholder:text-slate-400 ${
                  confirmPassword && password !== confirmPassword
                    ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                    : 'border-slate-300 focus:ring-indigo-500 focus:border-indigo-500'
                }`}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <>
                  <Spinner size="sm" />
                  <span>Creating account...</span>
                </>
              ) : (
                'Create Account & Sign In'
              )}
            </button>
          </form>

          {/* Switch to Login */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <p className="text-xs text-slate-600">
              Already have an account?{' '}
              <Link to="/login" className="font-bold text-indigo-600 hover:text-indigo-700 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Footer Note */}
        <p className="mt-6 text-center text-[11px] text-slate-400">
          By registering, you agree to comply with exam integrity &amp; proctoring regulations
        </p>
      </div>
    </div>
  )
}
