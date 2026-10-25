/**
 * components/AIAssistantWidget.tsx
 * Omnipresent AI Assistant, Doubt Solver & Exam Malpractice Monitor.
 *
 * Capabilities:
 * 1. Live Exam Malpractice Monitor & Academic Integrity Shield:
 *    - Detects and tracks browser telemetry (tab switches, focus lost, clipboard paste).
 *    - Shields exam integrity by preventing direct answer reveals during active tests.
 *    - Real-time Integrity Trust Score calculation (0-100%) and incident timeline.
 * 2. Academic Doubt Solver & Socratic Mentor:
 *    - Solves science/math doubts before and after exams with rich LaTeX KaTeX math ($...$ and $$...$$).
 *    - Explains misconceptions from past results and breaks down MIRT cognitive dimensions.
 *    - Provides portal and exam strategy navigation.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import client from '../api/client'
import MathText from './MathText'
import Spinner from './Spinner'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  mode?: string
  integrity_flag?: boolean
  timestamp: string
}

interface Incident {
  type: string
  label: string
  time: string
  severity: string
}

interface TelemetryStatus {
  session_id: string | null
  integrity_score: number
  verdict: 'clean' | 'caution' | 'flagged'
  status_label: string
  status_color: string
  breakdown: {
    tab_switches: number
    focus_losses: number
    camera_blocked: number
    cheat_attempts: number
    clipboard_pastes: number
    total_incidents: number
  }
  recent_incidents: Incident[]
}

export default function AIAssistantWidget() {
  const location = useLocation()
  const params = useParams()

  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'monitor'>('chat')
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [telemetry, setTelemetry] = useState<TelemetryStatus | null>(null)
  const [alertNotice, setAlertNotice] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Determine current exam session context
  const isExamSession = location.pathname.includes('/exam/session')
  const isExamResults = location.pathname.includes('/exam/results')
  const currentSessionId = location.pathname.split('/').pop() || null

  // Initial welcome message based on active route
  const getInitialMessage = useCallback((): string => {
    if (isExamSession) {
      return (
        `### 🛡️ Exam Integrity Guard & Guide Active\n\n` +
        `I am monitoring your active exam session to verify examination integrity.\n\n` +
        `- I **can** clarify terminology, exam timing, or the $+4 / -1$ marking scheme.\n` +
        `- Direct answer revelations ($A, B, C, D$) are **strictly locked** to protect academic honesty.\n\n` +
        `Stay calm, pace yourself, and focus on one question at a time!`
      )
    }
    if (isExamResults) {
      return (
        `### 💡 Post-Exam Doubt Solver & Diagnostic Review\n\n` +
        `Congratulations on completing your exam! I am here to:\n\n` +
        `1. Explain step-by-step solutions to any question you missed.\n` +
        `2. Break down your **Multidimensional IRT (MIRT)** cognitive profile.\n` +
        `3. Address any scientific or mathematical doubt with LaTeX formulas ($...$).\n\n` +
        `Which question or concept would you like to explore?`
      )
    }
    return (
      `### 👋 Hello! I'm Aura, your AI Academic Mentor & Exam Guide\n\n` +
      `I can help you with:\n` +
      `- **Doubt Solving:** Ask any math, physics, chemistry, or CS question with step-by-step LaTeX derivations.\n` +
      `- **Exam Strategy:** Master $+4 / -1$ entrance marking patterns & Thompson Sampling adaptive exams.\n` +
      `- **Integrity Monitoring:** Track your session trust score and exam activity.\n\n` +
      `How can I assist your preparation today?`
    )
  }, [isExamSession, isExamResults])

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: getInitialMessage(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ])

  // Update welcome message & reset activeTab if route fundamentally changes
  useEffect(() => {
    setActiveTab('chat')
    setMessages([
      {
        id: 'welcome-' + location.pathname,
        role: 'assistant',
        content: getInitialMessage(),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ])
  }, [location.pathname, getInitialMessage])

  // Fetch telemetry status
  const fetchTelemetry = useCallback(async () => {
    try {
      const qParams: Record<string, string> = {}
      if (currentSessionId && isExamSession) qParams.session_id = currentSessionId
      const res = await client.get('/ai-assistant/telemetry-status', { params: qParams })
      setTelemetry(res.data)
    } catch {
      // Degrade gracefully if backend unavailable
    }
  }, [currentSessionId, isExamSession])

  useEffect(() => {
    fetchTelemetry()
    // Poll telemetry during exam sessions
    if (isExamSession) {
      const interval = setInterval(fetchTelemetry, 6000)
      return () => clearInterval(interval)
    }
  }, [fetchTelemetry, isExamSession])

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (isOpen && activeTab === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen, activeTab])

  // Send message handler
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim()
    if (!text || loading) return

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    setMessages((prev) => [...prev, userMsg])
    if (!textToSend) setInputMessage('')
    setLoading(true)

    try {
      const historyPayload = messages
        .filter((m) => m.id !== 'welcome')
        .map((m) => ({ role: m.role, content: m.content }))

      const res = await client.post('/ai-assistant/chat', {
        message: text,
        context: {
          route: location.pathname,
          exam_session_id: currentSessionId,
          exam_type: isExamSession ? 'live' : undefined,
          is_finished: isExamResults
        },
        history: historyPayload
      })

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.data.response,
        mode: res.data.mode,
        integrity_flag: res.data.integrity_flag,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }

      setMessages((prev) => [...prev, botMsg])

      // If an academic integrity warning was triggered, display notice and refresh telemetry
      if (res.data.integrity_flag) {
        setAlertNotice('Academic Integrity Alert: Live answer retrieval attempt logged.')
        setTimeout(() => setAlertNotice(null), 5000)
        fetchTelemetry()
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '⚠️ I encountered a temporary connection issue. Please verify your query or try again in a moment.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  // Quick Action Chips
  const quickChips = isExamSession
    ? [
        'Explain marking scheme (+4 / -1)',
        'What does adiabatic process mean?',
        'Time management tips',
        'Help with question wording'
      ]
    : isExamResults
    ? [
        'Explain Doppler effect formula',
        'Why was my answer wrong?',
        'Break down my MIRT score',
        'Recommend study topics'
      ]
    : [
        'Explain Bernoulli\'s equation',
        'How does adaptive testing work?',
        'Solve: $\\int x e^x dx$',
        'Tips for JEE / entrance exams'
      ]

  return (
    <>
      {/* =================================================================== */}
      {/* FLOATING ACTION TRIGGER (BOTTOM-RIGHT)                             */}
      {/* =================================================================== */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
        {/* Proactive alert popover if integrity flag triggered */}
        {alertNotice && !isOpen && (
          <div className="bg-red-600 text-white text-xs px-3 py-2 rounded-lg shadow-xl animate-bounce max-w-xs flex items-center gap-2">
            <span>🛡️</span>
            <span>{alertNotice}</span>
          </div>
        )}

        <button
          onClick={() => setIsOpen(!isOpen)}
          data-testid="ai-assistant-toggle"
          className={`flex items-center gap-2.5 px-4 py-3 rounded-full shadow-2xl transition-all duration-300 transform hover:scale-105 ${
            isExamSession
              ? 'bg-gradient-to-r from-amber-600 to-indigo-700 text-white ring-2 ring-amber-300'
              : 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white hover:from-indigo-700 hover:to-blue-700'
          }`}
          title="Open Aura AI Guide & Doubt Solver"
        >
          {/* Animated pulse indicator */}
          <div className="relative flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
            <span className="absolute w-2.5 h-2.5 rounded-full bg-green-400 animate-ping opacity-75" />
          </div>

          <span className="text-base font-bold">
            {isExamSession ? '🛡️ Proctor & Guide' : '✨ Aura AI Tutor'}
          </span>

          {telemetry && telemetry.breakdown.total_incidents > 0 && (
            <span className="bg-red-500 text-white text-[10px] font-extrabold px-1.5 py-0.5 rounded-full">
              {telemetry.breakdown.total_incidents}
            </span>
          )}
        </button>
      </div>

      {/* =================================================================== */}
      {/* EXPANDED ASSISTANT DRAWER / PANEL                                  */}
      {/* =================================================================== */}
      {isOpen && (
        <div
          data-testid="ai-assistant-drawer"
          className="fixed bottom-20 right-6 z-50 w-96 md:w-[440px] h-[580px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200"
        >
          {/* Header Bar */}
          <div className="bg-gray-900 text-white px-5 py-3.5 flex items-center justify-between border-b border-gray-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-sm shadow">
                {isExamSession ? '🛡️' : '🤖'}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-sm tracking-wide">Aura AI</h3>
                  <span className="text-[10px] bg-green-500/20 text-green-300 border border-green-500/30 px-1.5 py-0.2 rounded font-semibold">
                    {isExamSession ? 'Integrity Proctor' : 'Doubt Solver'}
                  </span>
                </div>
                <p className="text-[11px] text-gray-400">
                  {isExamSession
                    ? 'Monitoring examination activity & integrity'
                    : isExamResults
                    ? 'Post-exam concept remediation'
                    : 'Universal STEM & Exam Guide'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setMessages([{ id: 'reset', role: 'assistant', content: getInitialMessage(), timestamp: '' }])}
                title="Reset conversation"
                className="text-gray-400 hover:text-white p-1.5 rounded-md hover:bg-gray-800 text-xs transition-colors"
              >
                ↺
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-white p-1.5 rounded-md hover:bg-gray-800 text-sm transition-colors"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="grid grid-cols-2 bg-gray-50 border-b border-gray-200 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('chat')}
              className={`py-2.5 text-center transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'chat'
                  ? 'border-b-2 border-indigo-600 text-indigo-700 bg-white font-bold'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <span>💬</span> Doubt Solver & Guide
            </button>
            <button
              onClick={() => {
                setActiveTab('monitor')
                fetchTelemetry()
              }}
              className={`py-2.5 text-center transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'monitor'
                  ? 'border-b-2 border-indigo-600 text-indigo-700 bg-white font-bold'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <span>🛡️</span> Integrity Monitor
              {telemetry && telemetry.breakdown.total_incidents > 0 && (
                <span className="w-2 h-2 rounded-full bg-red-500" />
              )}
            </button>
          </div>

          {/* Tab 1: Doubt Solver & Chat */}
          {activeTab === 'chat' && (
            <div className="flex-1 flex flex-col min-h-0 bg-gray-50/50">
              {/* Message History */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs">
                {messages.map((m) => {
                  const isUser = m.role === 'user'
                  return (
                    <div
                      key={m.id}
                      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed shadow-sm ${
                          isUser
                            ? 'bg-indigo-600 text-white rounded-br-none'
                            : m.integrity_flag
                            ? 'bg-amber-50 border-2 border-amber-300 text-gray-900 rounded-bl-none'
                            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'
                        }`}
                      >
                        {m.integrity_flag && (
                          <div className="flex items-center gap-1.5 text-amber-700 font-bold mb-1 pb-1 border-b border-amber-200 text-[11px]">
                            <span>🛡️</span> Academic Integrity Shield Activated
                          </div>
                        )}
                        <MathText text={m.content} />
                      </div>
                      <span className="text-[10px] text-gray-400 mt-1 px-1">
                        {m.timestamp}
                      </span>
                    </div>
                  )
                })}
                {loading && (
                  <div className="flex items-center gap-2 bg-white border border-gray-200 text-gray-500 px-3 py-2 rounded-xl text-xs w-fit shadow-sm">
                    <Spinner size="sm" />
                    <span>Aura is calculating step-by-step reasoning...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Quick Action Suggestion Chips */}
              <div className="px-3 py-2 bg-white border-t border-gray-100 flex gap-1.5 overflow-x-auto text-[11px]">
                {quickChips.map((chip, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(chip)}
                    disabled={loading}
                    className="whitespace-nowrap px-2.5 py-1 rounded-full bg-gray-100 hover:bg-indigo-50 hover:text-indigo-700 text-gray-600 transition-colors border border-gray-200 shrink-0"
                  >
                    {chip}
                  </button>
                ))}
              </div>

              {/* Input Box */}
              <div className="p-3 bg-white border-t border-gray-200 flex items-center gap-2">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder={
                    isExamSession
                      ? 'Ask about wording, time, or exam rules...'
                      : 'Ask any STEM doubt, formula, or question...'
                  }
                  disabled={loading}
                  data-testid="ai-assistant-input"
                  className="flex-1 text-xs border border-gray-300 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={loading || !inputMessage.trim()}
                  data-testid="ai-assistant-send"
                  className="px-3.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-colors shadow-sm"
                >
                  ➤
                </button>
              </div>
            </div>
          )}

          {/* Tab 2: Integrity & Malpractice Monitor */}
          {activeTab === 'monitor' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs bg-gray-50">
              {/* Trust Score Banner */}
              <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-gray-400 uppercase font-bold tracking-wider">
                    Candidate Integrity Trust Score
                  </span>
                  <div className="text-2xl font-black text-gray-900 mt-0.5">
                    {telemetry ? `${telemetry.integrity_score}%` : '100%'}
                  </div>
                  <span
                    className={`inline-block mt-1 text-[10px] font-bold px-2 py-0.5 rounded ${
                      telemetry?.verdict === 'clean'
                        ? 'bg-green-100 text-green-800'
                        : telemetry?.verdict === 'caution'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {telemetry?.status_label || 'Clean & Verified'}
                  </span>
                </div>
                <div className="w-14 h-14 rounded-full border-4 flex items-center justify-center font-bold text-lg bg-gray-50 border-indigo-600 text-indigo-700">
                  🛡️
                </div>
              </div>

              {/* Malpractice Telemetry Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white border rounded-lg p-2.5 shadow-sm">
                  <span className="text-gray-500 text-[11px] block">Tab Switches</span>
                  <span className="text-base font-bold text-gray-900">
                    {telemetry?.breakdown.tab_switches ?? 0}
                  </span>
                </div>
                <div className="bg-white border rounded-lg p-2.5 shadow-sm">
                  <span className="text-gray-500 text-[11px] block">Focus Losses</span>
                  <span className="text-base font-bold text-gray-900">
                    {telemetry?.breakdown.focus_losses ?? 0}
                  </span>
                </div>
                <div className="bg-white border rounded-lg p-2.5 shadow-sm">
                  <span className="text-gray-500 text-[11px] block">Camera Drops</span>
                  <span className="text-base font-bold text-gray-900">
                    {telemetry?.breakdown.camera_blocked ?? 0}
                  </span>
                </div>
                <div className="bg-white border rounded-lg p-2.5 shadow-sm">
                  <span className="text-gray-500 text-[11px] block">Cheat Inquiries</span>
                  <span className="text-base font-bold text-red-600">
                    {telemetry?.breakdown.cheat_attempts ?? 0}
                  </span>
                </div>
              </div>

              {/* Incident Feed */}
              <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-2.5">
                <h4 className="font-bold text-gray-800 text-xs border-b pb-1.5 flex items-center justify-between">
                  <span>Recent Security Audit Feed</span>
                  <span className="text-[10px] text-gray-400 font-normal">Live Telemetry</span>
                </h4>

                {telemetry && telemetry.recent_incidents.length > 0 ? (
                  <div className="space-y-2">
                    {telemetry.recent_incidents.map((inc, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-2 rounded bg-gray-50 border text-[11px]"
                      >
                        <span className="text-amber-500 mt-0.5">⚠️</span>
                        <div className="flex-1">
                          <p className="font-semibold text-gray-800">{inc.label}</p>
                          <span className="text-[10px] text-gray-400">{inc.time}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-5 text-gray-400">
                    <span className="text-xl block mb-1">✅</span>
                    <p className="text-[11px]">No malpractice signals detected.</p>
                    <p className="text-[10px] text-gray-400">Session compliance rating is optimal.</p>
                  </div>
                )}
              </div>

              {/* Proctor Advice Card */}
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-[11px] text-indigo-900 leading-relaxed">
                <span className="font-bold block mb-0.5">🔒 Automated Proctor Protocol:</span>
                Browser events and camera angles are logged in real time. Flagged examinations undergo secondary human reviewer audit before final score certification.
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
