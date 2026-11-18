/**
 * pages/ForgotPassword.tsx
 * Multi-step password reset flow:
 * 1. Request OTP via email (POST /forgot-password)
 * 2. Enter and verify 6-digit OTP (POST /verify-otp) -> receives signed reset_token
 * 3. Enter and confirm new password (POST /reset-password)
 * 4. Success confirmation with auto-redirect to /login
 */
import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'

type Step = 'REQUEST' | 'VERIFY' | 'RESET' | 'SUCCESS'

export default function ForgotPassword() {
  const navigate = useNavigate()

  // State
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
      navigate('/login', { replace: true })
      return
    }
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [step, countdown, navigate])

  // 1. Submit email to receive OTP
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfoMessage(null)
    setDevOtpNotice(null)

    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setError('Please enter your email address.')
      return
    }

    setLoading(true)
    try {
      const res = await client.post('/forgot-password', { email: trimmedEmail })
      const data = res.data
      setInfoMessage(data.message || 'Verification code sent to your email.')
      if (data.dev_otp) {
        setDevOtpNotice(`Development Mode: Your verification code is ${data.dev_otp}`)
      }
      setResendCooldown(60)
      setStep('VERIFY')
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string | Array<{ msg: string }> } }
      }
      if (!axiosErr.response) {
        setError('Cannot connect to backend server. Please verify start_server.bat is running.')
      } else {
        const detail = axiosErr.response.data?.detail
        if (typeof detail === 'string') {
          setError(detail)
        } else if (Array.isArray(detail) && detail.length > 0) {
          setError(detail.map((d) => d.msg).join(', '))
        } else {
          setError('Failed to send verification code. Please ensure your email is registered.')
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
      const res = await client.post('/forgot-password', { email: email.trim() })
      const data = res.data
      setInfoMessage('A new verification code has been sent.')
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

    const cleanOtp = otp.trim()
    if (cleanOtp.length !== 6 || !/^\d{6}$/.test(cleanOtp)) {
      setError('Please enter the valid 6-digit numeric verification code.')
      return
    }

    setLoading(true)
    try {
      const res = await client.post('/verify-otp', {
        email: email.trim(),
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
      const axiosErr = err as {
        response?: { data?: { detail?: string | Array<{ msg: string }> } }
      }
      if (!axiosErr.response) {
        setError('Cannot connect to backend server. Please verify start_server.bat is running.')
      } else {
        const detail = axiosErr.response.data?.detail
        setError(typeof detail === 'string' ? detail : 'Invalid or expired verification code.')
      }
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
      setError('Passwords do not match. Please re-enter.')
      return
    }

    setLoading(true)
    try {
      await client.post('/reset-password', {
        email: email.trim(),
        reset_token: resetToken,
        new_password: newPassword,
      })
      setStep('SUCCESS')
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { detail?: string | Array<{ msg: string }> } }
      }
      if (!axiosErr.response) {
        setError('Cannot connect to backend server. Please verify start_server.bat is running.')
      } else {
        const detail = axiosErr.response.data?.detail
        setError(
          typeof detail === 'string'
            ? detail
            : 'Failed to reset password. The verification session may have expired.'
        )
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h1 className="text-center text-3xl font-bold text-gray-900">Intelligent Exam Portal</h1>
        <h2 className="mt-2 text-center text-lg text-gray-600">
          {step === 'REQUEST' && 'Reset your password'}
          {step === 'VERIFY' && 'Verify your email'}
          {step === 'RESET' && 'Set new password'}
          {step === 'SUCCESS' && 'Password updated'}
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-md rounded-lg sm:px-10">
          {/* Progress Indicator */}
          {step !== 'SUCCESS' && (
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-100">
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    step === 'REQUEST'
                      ? 'bg-blue-600 text-white'
                      : 'bg-green-600 text-white'
                  }`}
                >
                  {step === 'REQUEST' ? '1' : '✓'}
                </span>
                <span className="text-xs font-medium text-gray-600">Email</span>
              </div>
              <div className="flex-1 h-0.5 bg-gray-200 mx-2" />
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    step === 'VERIFY'
                      ? 'bg-blue-600 text-white'
                      : step === 'RESET'
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {step === 'RESET' ? '✓' : '2'}
                </span>
                <span className="text-xs font-medium text-gray-600">OTP Code</span>
              </div>
              <div className="flex-1 h-0.5 bg-gray-200 mx-2" />
              <div className="flex items-center space-x-2">
                <span
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                    step === 'RESET'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  3
                </span>
                <span className="text-xs font-medium text-gray-600">Password</span>
              </div>
            </div>
          )}

          {/* Feedback & Alert Messages */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-300 rounded-md">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
          {infoMessage && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-700">{infoMessage}</p>
            </div>
          )}
          {devOtpNotice && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-md">
              <p className="text-xs font-mono text-amber-800 font-semibold">{devOtpNotice}</p>
            </div>
          )}

          {/* STEP 1: Request OTP */}
          {step === 'REQUEST' && (
            <form onSubmit={handleRequestOtp} className="space-y-5">
              <p className="text-sm text-gray-600">
                Enter your account email address and we&apos;ll send you a 6-digit verification code to
                reset your password.
              </p>
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                  placeholder="you@example.com"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading && <Spinner size="sm" />}
                {loading ? 'Sending verification code...' : 'Send Verification Code'}
              </button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="text-sm font-medium text-blue-600 hover:text-blue-500 hover:underline"
                >
                  ← Back to Login
                </Link>
              </div>
            </form>
          )}

          {/* STEP 2: Verify OTP */}
          {step === 'VERIFY' && (
            <form onSubmit={handleVerifyOtp} className="space-y-5">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">
                    Code sent to <strong className="text-gray-900">{email}</strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setStep('REQUEST')
                      setError(null)
                      setInfoMessage(null)
                    }}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Change
                  </button>
                </div>
              </div>

              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700">
                  Enter 6-digit Code
                </label>
                <input
                  id="otp"
                  type="text"
                  maxLength={6}
                  required
                  autoFocus
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  className="mt-1 block w-full px-3 py-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl font-mono tracking-widest font-bold"
                  placeholder="000000"
                />
                <p className="mt-1 text-xs text-gray-500 text-center">
                  Code expires in 10 minutes.
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full flex justify-center items-center gap-2 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading && <Spinner size="sm" />}
                {loading ? 'Verifying code...' : 'Verify Code'}
              </button>

              <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
                <span>Didn&apos;t receive code?</span>
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={resendCooldown > 0 || loading}
                  className="font-medium text-blue-600 hover:text-blue-500 disabled:text-gray-400 disabled:cursor-not-allowed"
                >
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code'}
                </button>
              </div>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="text-sm font-medium text-blue-600 hover:text-blue-500 hover:underline"
                >
                  ← Back to Login
                </Link>
              </div>
            </form>
          )}

          {/* STEP 3: Set New Password */}
          {step === 'RESET' && (
            <form onSubmit={handleResetPassword} className="space-y-5">
              <p className="text-sm text-gray-600">
                Identity verified! Create a new secure password for your account.
              </p>

              <div>
                <label
                  htmlFor="new-password"
                  className="block text-sm font-medium text-gray-700"
                >
                  New Password
                </label>
                <div className="relative mt-1">
                  <input
                    id="new-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                    placeholder="At least 6 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-gray-500 hover:text-gray-700"
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>

              <div>
                <label
                  htmlFor="confirm-password"
                  className="block text-sm font-medium text-gray-700"
                >
                  Confirm New Password
                </label>
                <input
                  id="confirm-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                  placeholder="Re-enter new password"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading && <Spinner size="sm" />}
                {loading ? 'Updating password...' : 'Update Password'}
              </button>
            </form>
          )}

          {/* STEP 4: Success */}
          {step === 'SUCCESS' && (
            <div className="text-center py-4 space-y-4">
              <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto text-3xl font-bold">
                ✓
              </div>
              <h3 className="text-xl font-bold text-gray-900">Password Reset Successful</h3>
              <p className="text-sm text-gray-600">
                Your password has been changed securely. You can now use your new password to sign
                in.
              </p>
              <p className="text-xs text-gray-500">
                Redirecting to login in {countdown} second{countdown === 1 ? '' : 's'}...
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => navigate('/login', { replace: true })}
                  className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Proceed to Login Now
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
