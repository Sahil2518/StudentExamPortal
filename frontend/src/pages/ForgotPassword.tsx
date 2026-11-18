/**
 * pages/ForgotPassword.tsx
 * Modern, enterprise-grade password recovery flow.
 * Steps:
 * 1. Request OTP via email (POST /forgot-password)
 * 2. Enter and verify 6-digit OTP (POST /verify-otp) -> receives signed reset_token
 * 3. Enter and confirm new password (POST /reset-password)
 * 4. Success confirmation with auto-redirect to /login
 */
import React, { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'

type Step = 'REQUEST' | 'VERIFY' | 'RESET' | 'SUCCESS'

export default function ForgotPassword() {
  const navigate = useNavigate()

  // Form State
  const [step, setStep] = useState<Step>('REQUEST')
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  // Status & Feedback
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [devOtpNotice, setDevOtpNotice] = useState<string | null>(null)

  // Resend cooldown timer (60 seconds)
  const [resendCooldown, setResendCooldown] = useState(0)

  // Success redirect countdown (5 seconds)
  const [countdown, setCountdown] = useState(5)

  // Cooldown effect
  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [resendCooldown])

  // Success auto-redirect effect
  useEffect(() => {
    if (step !== 'SUCCESS') return
    if (countdown <= 0) {
      navigate('/login', { replace: true, state: { resetSuccess: true } })
      return
    }
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [step, countdown, navigate])

  // Password strength calculation
  const passwordStrength = useMemo(() => {
    if (!newPassword) return 0
    let score = 0
    if (newPassword.length >= 6) score += 1
    if (newPassword.length >= 10) score += 1
    if (/[0-9]/.test(newPassword)) score += 1
    if (/[^A-Za-z0-9]/.test(newPassword) || (/[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword))) score += 1
    return score
  }, [newPassword])

  const strengthLabels = ['', 'Weak', 'Fair', 'Good', 'Strong']
  const strengthColors = ['', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500']

  // 1. Submit email to receive OTP
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)
    setDevOtpNotice(null)

    const cleanEmail = email.trim().toLowerCase()
    if (!cleanEmail) {
      setError('Please enter your email address.')
      return
    }

    setLoading(true)
    try {
      const res = await client.post('/forgot-password', { email: cleanEmail })
      const data = res.data
      setInfoMessage(data.message || 'Verification code sent to your email.')
      if (data.email) {
        setEmail(data.email)
      }
      if (data.dev_otp) {
        setDevOtpNotice(`Development Mode: Your verification code is ${data.dev_otp}`)
      }
      setResendCooldown(60)
      setStep('VERIFY')
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
        const detail = axiosErr.response.data?.detail
        if (typeof detail === 'string') {
          setError(detail)
        } else if (Array.isArray(detail) && detail.length > 0) {
          setError(detail.map((d) => d.msg).join(', '))
        } else {
          setError('No account found with this email. Please check your spelling or register a new account.')
        }
      }
    } finally {
      setLoading(false)
    }
  }

  // Resend OTP handler
  const handleResendOtp = async () => {
    if (resendCooldown > 0 || loading) return
    setError(null)
    setInfoMessage(null)
    setDevOtpNotice(null)

    setLoading(true)
    try {
      const res = await client.post('/forgot-password', { email: email.trim().toLowerCase() })
      const data = res.data
      setInfoMessage('A new verification code has been sent to your email.')
      if (data.dev_otp) {
        setDevOtpNotice(`Development Mode: Your verification code is ${data.dev_otp}`)
      }
      setResendCooldown(60)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Failed to resend code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // 2. Submit OTP to verify and receive reset_token
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)

    const cleanOtp = otp.trim().replace(/\s+/g, '')
    if (cleanOtp.length !== 6 || !/^\d{6}$/.test(cleanOtp)) {
      setError('Please enter the complete 6-digit verification code.')
      return
    }

    setLoading(true)
    try {
      const res = await client.post('/verify-otp', {
        email: email.trim().toLowerCase(),
        otp: cleanOtp,
      })
      const data = res.data
      if (data.reset_token) {
        setResetToken(data.reset_token)
        setStep('RESET')
      } else {
        setError('Verification succeeded but reset token was not received.')
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Invalid or expired verification code. Please check and try again.')
    } finally {
      setLoading(false)
    }
  }

  // 3. Submit new password with reset_token
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters long.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please verify and re-enter.')
      return
    }

    setLoading(true)
    try {
      await client.post('/reset-password', {
        email: email.trim().toLowerCase(),
        reset_token: resetToken,
        new_password: newPassword,
      })
      setStep('SUCCESS')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(
        axiosErr.response?.data?.detail ||
          'Failed to reset password. Your verification session may have expired. Please restart the request.'
      )
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
          Intelligent Exam Portal
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          {step === 'REQUEST' && 'Recover your account password'}
          {step === 'VERIFY' && 'Verify your identity'}
          {step === 'RESET' && 'Create your new password'}
          {step === 'SUCCESS' && 'Password updated successfully'}
        </p>
      </div>

      {/* Auth Card */}
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl shadow-slate-200/50 rounded-2xl border border-slate-100 sm:px-10">
          {/* Progress Indicator Steps */}
          {step !== 'SUCCESS' && (
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                    step === 'REQUEST'
                      ? 'bg-indigo-600 text-white ring-4 ring-indigo-100'
                      : 'bg-emerald-600 text-white'
                  }`}
                >
                  {step === 'REQUEST' ? '1' : '✓'}
                </span>
                <span className="text-xs font-semibold text-slate-700">Email</span>
              </div>
              <div className="flex-1 h-0.5 bg-slate-200 mx-2" />
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                    step === 'VERIFY'
                      ? 'bg-indigo-600 text-white ring-4 ring-indigo-100'
                      : step === 'RESET'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {step === 'RESET' ? '✓' : '2'}
                </span>
                <span className="text-xs font-semibold text-slate-700">Verify</span>
              </div>
              <div className="flex-1 h-0.5 bg-slate-200 mx-2" />
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                    step === 'RESET'
                      ? 'bg-indigo-600 text-white ring-4 ring-indigo-100'
                      : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  3
                </span>
                <span className="text-xs font-semibold text-slate-700">Password</span>
              </div>
            </div>
          )}

          {/* Feedback & Alert Banners */}
          {error && (
            <div className="mb-5 p-3.5 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2.5 text-xs text-red-800 animate-in fade-in duration-200">
              <span className="text-base text-red-600">⚠️</span>
              <span className="font-medium pt-0.5">{error}</span>
            </div>
          )}
          {infoMessage && (
            <div className="mb-5 p-3.5 bg-indigo-50 border border-indigo-200 rounded-xl flex items-start gap-2.5 text-xs text-indigo-800 animate-in fade-in duration-200">
              <span className="text-base text-indigo-600">ℹ️</span>
              <span className="font-medium pt-0.5">{infoMessage}</span>
            </div>
          )}
          {devOtpNotice && (
            <div className="mb-5 p-3.5 bg-amber-50 border border-amber-300 rounded-xl text-xs font-mono text-amber-900 font-semibold animate-in fade-in duration-200">
              {devOtpNotice}
            </div>
          )}

          {/* =========================================================================
              STEP 1: Request OTP Email
              ========================================================================= */}
          {step === 'REQUEST' && (
            <form onSubmit={handleRequestOtp} className="space-y-4">
              <p className="text-xs text-slate-600 leading-relaxed">
                Enter your registered candidate email address. We will send you a 6-digit verification code to reset your password.
              </p>

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

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <>
                    <Spinner size="sm" />
                    <span>Sending code...</span>
                  </>
                ) : (
                  'Send Verification Code'
                )}
              </button>

              <div className="pt-4 text-center">
                <Link to="/login" className="text-xs font-semibold text-slate-600 hover:text-indigo-600">
                  ← Back to Sign In
                </Link>
              </div>
            </form>
          )}

          {/* =========================================================================
              STEP 2: Enter & Verify 6-digit OTP
              ========================================================================= */}
          {step === 'VERIFY' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span>
                  Code sent to <strong className="text-slate-900">{email}</strong>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setStep('REQUEST')
                    setError(null)
                    setInfoMessage(null)
                  }}
                  className="text-indigo-600 hover:underline font-semibold"
                >
                  Change
                </button>
              </div>

              <div>
                <label htmlFor="otp" className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5 text-center">
                  Enter 6-Digit Code
                </label>
                <input
                  id="otp"
                  type="text"
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="w-full px-4 py-3 text-2xl font-mono font-extrabold tracking-[0.5em] text-center bg-slate-50 border-2 border-indigo-200 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all text-slate-900"
                />
                <p className="mt-1.5 text-[11px] text-center text-slate-400">
                  Verification code expires in 10 minutes
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || otp.trim().length !== 6}
                className="w-full flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <>
                    <Spinner size="sm" />
                    <span>Verifying code...</span>
                  </>
                ) : (
                  'Verify Code & Continue'
                )}
              </button>

              <div className="pt-2 flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={resendCooldown > 0 || loading}
                  className="font-semibold text-indigo-600 hover:underline disabled:text-slate-400 disabled:no-underline"
                >
                  {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
                </button>
                <Link to="/login" className="text-slate-500 hover:text-slate-700">
                  Cancel
                </Link>
              </div>
            </form>
          )}

          {/* =========================================================================
              STEP 3: Set New Password
              ========================================================================= */}
          {step === 'RESET' && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="newPassword" className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                    New Password
                  </label>
                  {newPassword && (
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${
                      passwordStrength <= 1 ? 'text-red-500' : passwordStrength === 2 ? 'text-amber-500' : 'text-emerald-600'
                    }`}>
                      {strengthLabels[passwordStrength]}
                    </span>
                  )}
                </div>

                <div className="relative">
                  <input
                    id="newPassword"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
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

                {newPassword && (
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

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="confirmPassword" className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                    Confirm New Password
                  </label>
                  {confirmPassword && (
                    <span className={`text-[10px] font-bold ${
                      newPassword === confirmPassword ? 'text-emerald-600' : 'text-red-500'
                    }`}>
                      {newPassword === confirmPassword ? '✓ Passwords match' : '✕ Must match'}
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
                  placeholder="Re-enter your new password"
                  className={`w-full px-3.5 py-2.5 text-sm bg-slate-50 border rounded-xl focus:bg-white focus:outline-none focus:ring-2 transition-all placeholder:text-slate-400 ${
                    confirmPassword && newPassword !== confirmPassword
                      ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                      : 'border-slate-300 focus:ring-indigo-500 focus:border-indigo-500'
                  }`}
                />
              </div>

              <button
                type="submit"
                disabled={loading || newPassword.length < 6 || newPassword !== confirmPassword}
                className="w-full mt-2 flex justify-center items-center gap-2 py-3 px-4 border border-transparent rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <>
                    <Spinner size="sm" />
                    <span>Updating password...</span>
                  </>
                ) : (
                  'Set New Password & Complete'
                )}
              </button>
            </form>
          )}

          {/* =========================================================================
              STEP 4: Success Screen
              ========================================================================= */}
          {step === 'SUCCESS' && (
            <div className="text-center space-y-4 py-2 animate-in zoom-in-95 duration-200">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl mx-auto shadow-inner">
                ✓
              </div>
              <h3 className="text-xl font-bold text-slate-900">Password Updated Successfully!</h3>
              <p className="text-xs text-slate-600 leading-relaxed max-w-sm mx-auto">
                Your credentials have been securely updated. You will be redirected to the sign-in page in{' '}
                <strong className="text-indigo-600">{countdown}s</strong>.
              </p>
              <button
                type="button"
                onClick={() => navigate('/login', { replace: true, state: { resetSuccess: true } })}
                className="w-full mt-4 py-3 px-4 rounded-xl shadow-md text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all"
              >
                Sign In With New Password →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
