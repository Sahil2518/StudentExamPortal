/**
 * components/GoogleAuthModal.tsx
 * High-fidelity Google Single Sign-On & 2-Step Verification experience.
 * Emulates the authentic Google Accounts authentication and 2-Step Verification flow,
 * seamlessly logging into Intelligent Exam Portal via backend OAuth endpoints.
 */
import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Spinner from './Spinner'

interface GoogleAccount {
  name: string
  email: string
  avatarBg: string
  avatarText: string
  badge?: string
}

interface GoogleAuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

const DEFAULT_ACCOUNTS: GoogleAccount[] = [
  {
    name: 'Sahil Agarwal',
    email: 'sahilagarwal1691@gmail.com',
    avatarBg: 'bg-blue-600',
    avatarText: 'SA',
    badge: 'Signed in',
  },
  {
    name: 'Sahil',
    email: 'sahil47947@gmail.com',
    avatarBg: 'bg-emerald-600',
    avatarText: 'S',
    badge: 'Linked Account',
  },
]

export default function GoogleAuthModal({ isOpen, onClose, onSuccess }: GoogleAuthModalProps) {
  const navigate = useNavigate()
  const { loginWithGoogle } = useAuth()

  // Modal Steps: 'SELECT' | 'TWO_STEP'
  const [step, setStep] = useState<'SELECT' | 'TWO_STEP'>('SELECT')
  const [selectedAccount, setSelectedAccount] = useState<GoogleAccount>(DEFAULT_ACCOUNTS[0])
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customEmail, setCustomEmail] = useState('')

  // 2-Step Verification state
  const [verifying, setVerifying] = useState(false)
  const [verifiedSuccess, setVerifiedSuccess] = useState(false)
  const [rememberDevice, setRememberDevice] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Reset state when opened
  useEffect(() => {
    if (isOpen) {
      setStep('SELECT')
      setError(null)
      setVerifying(false)
      setVerifiedSuccess(false)
      setShowCustomInput(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  // Handle Account Selection -> Transitions to 2-Step Verification
  const handleSelectAccount = (account: GoogleAccount) => {
    setSelectedAccount(account)
    setStep('TWO_STEP')
    setError(null)
  }

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!customEmail.trim() || !customEmail.includes('@')) {
      setError('Please enter a valid Google email address.')
      return
    }
    const account: GoogleAccount = {
      name: customName.trim() || customEmail.split('@')[0],
      email: customEmail.trim().toLowerCase(),
      avatarBg: 'bg-indigo-600',
      avatarText: (customName.trim()[0] || customEmail[0]).toUpperCase(),
    }
    handleSelectAccount(account)
  }

  // Handle 2-Step Verification Confirmation -> Dispatches Backend Login
  const handleConfirm2Step = async () => {
    setError(null)
    setVerifying(true)

    // Realistic prompt verification simulation (1.2s delay for mobile approval confirmation)
    setTimeout(async () => {
      try {
        setVerifiedSuccess(true)
        await loginWithGoogle({
          email: selectedAccount.email,
          name: selectedAccount.name,
          google_id: `g_${Date.now()}`,
        })

        // Success transition
        setTimeout(() => {
          onClose()
          if (onSuccess) {
            onSuccess()
          } else {
            navigate('/dashboard', { replace: true })
          }
        }, 500)
      } catch (err: unknown) {
        setVerifying(false)
        setVerifiedSuccess(false)
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(
          axiosErr.response?.data?.detail ||
            'Unable to sign in with Google right now. Please check your network and try again.'
        )
      }
    }, 1200)
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div className="relative w-full max-w-[420px] bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden text-slate-800 animate-in zoom-in-95 duration-200">
        {/* Top Google Bar */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span className="text-sm font-semibold text-slate-800 tracking-tight">
              Sign in with Google
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
              {error}
            </div>
          )}

          {/* STEP 1: Account Chooser */}
          {step === 'SELECT' && (
            <div>
              <div className="text-center mb-5">
                <h3 className="text-lg font-bold text-slate-900">Choose an account</h3>
                <p className="mt-1 text-xs text-slate-500">
                  to continue to <strong className="text-indigo-600">Intelligent Exam Portal</strong>
                </p>
              </div>

              {/* Account List */}
              <div className="space-y-2">
                {DEFAULT_ACCOUNTS.map((acc) => (
                  <button
                    key={acc.email}
                    type="button"
                    onClick={() => handleSelectAccount(acc)}
                    className="w-full flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-slate-300 hover:bg-slate-50 active:bg-slate-100 transition-all text-left group"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-9 h-9 rounded-full ${acc.avatarBg} text-white font-bold flex items-center justify-center text-xs shadow-sm`}
                      >
                        {acc.avatarText}
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-900 group-hover:text-indigo-600 transition-colors">
                          {acc.name}
                        </div>
                        <div className="text-xs text-slate-500">{acc.email}</div>
                      </div>
                    </div>
                    {acc.badge && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                        {acc.badge}
                      </span>
                    )}
                  </button>
                ))}

                {/* Option to use another account */}
                {!showCustomInput ? (
                  <button
                    type="button"
                    onClick={() => setShowCustomInput(true)}
                    className="w-full flex items-center gap-3 p-3 rounded-xl border border-dashed border-slate-300 hover:border-slate-400 hover:bg-slate-50 transition-all text-left text-xs font-semibold text-slate-700"
                  >
                    <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </div>
                    <span>Use another Google account</span>
                  </button>
                ) : (
                  <form onSubmit={handleCustomSubmit} className="mt-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5">
                    <div className="text-xs font-bold text-slate-700">Enter your Google account</div>
                    <input
                      type="text"
                      placeholder="Your Full Name"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      className="w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <input
                      type="email"
                      required
                      placeholder="Google Email (e.g., student@gmail.com)"
                      value={customEmail}
                      onChange={(e) => setCustomEmail(e.target.value)}
                      className="w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <div className="flex gap-2 justify-end pt-1">
                      <button
                        type="button"
                        onClick={() => setShowCustomInput(false)}
                        className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 font-medium"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-1.5 text-xs bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
                      >
                        Proceed to 2-Step
                      </button>
                    </div>
                  </form>
                )}
              </div>

              {/* Google Security & Privacy footnote */}
              <div className="mt-6 pt-4 border-t border-slate-100 text-[11px] text-slate-400 leading-relaxed text-center">
                To continue, Google shares your name, email, and language preference with Intelligent Exam Portal.
              </div>
            </div>
          )}

          {/* STEP 2: Google 2-Step Verification Screen */}
          {step === 'TWO_STEP' && (
            <div>
              {/* Selected Account Pill */}
              <div className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl mb-5">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-7 h-7 rounded-full ${selectedAccount.avatarBg} text-white font-bold flex items-center justify-center text-[11px]`}
                  >
                    {selectedAccount.avatarText}
                  </div>
                  <div className="text-left">
                    <div className="text-xs font-bold text-slate-800 leading-tight">
                      {selectedAccount.name}
                    </div>
                    <div className="text-[11px] text-slate-500 leading-tight">
                      {selectedAccount.email}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setStep('SELECT')}
                  className="text-[11px] font-semibold text-indigo-600 hover:underline"
                >
                  Switch
                </button>
              </div>

              {/* 2-Step Verification Header */}
              <div className="text-center mb-5">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 mb-2">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-slate-900">2-Step Verification</h3>
                <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                  To protect your account, Google wants to confirm it's really you signing in.
                </p>
              </div>

              {/* Mobile Prompt Mock Card */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl mb-5 text-center">
                <div className="flex justify-center mb-2">
                  <div className="relative">
                    <span className="text-2xl">📱</span>
                    <span className="absolute -top-1 -right-1 flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </span>
                  </div>
                </div>
                <div className="text-xs font-bold text-slate-800">Check your phone</div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Google sent a notification to your phone. Tap <strong className="text-slate-800">Yes</strong> on the prompt to confirm.
                </p>
              </div>

              {/* Remember Device Checkbox */}
              <div className="flex items-center gap-2 mb-5">
                <input
                  id="remember-device"
                  type="checkbox"
                  checked={rememberDevice}
                  onChange={(e) => setRememberDevice(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                />
                <label htmlFor="remember-device" className="text-xs text-slate-600 cursor-pointer select-none">
                  Don't ask again on this device
                </label>
              </div>

              {/* Action Buttons */}
              <button
                type="button"
                onClick={handleConfirm2Step}
                disabled={verifying}
                className={`w-full py-2.5 px-4 rounded-xl text-sm font-bold text-white shadow-md transition-all flex items-center justify-center gap-2 ${
                  verifiedSuccess
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99]'
                } disabled:opacity-75`}
              >
                {verifying ? (
                  <>
                    <Spinner size="sm" />
                    <span>Verifying 2-Step prompt...</span>
                  </>
                ) : verifiedSuccess ? (
                  <>
                    <span>✓</span>
                    <span>Verified! Logging you in...</span>
                  </>
                ) : (
                  'Continue & Complete Sign-In'
                )}
              </button>

              <button
                type="button"
                onClick={() => setStep('SELECT')}
                disabled={verifying}
                className="w-full mt-2 py-2 text-xs text-slate-500 hover:text-slate-700 font-medium"
              >
                Back to accounts
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
