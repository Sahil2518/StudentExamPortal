/**
 * pages/ExamSetup.tsx
 * Exam setup wizard - lets the student configure standardized competitive entrance exams
 * or AI adaptive practice sessions.
 * Supports:
 * - Full suite of National & Global Entrance Exams (JEE, NEET, GATE, CAT, UPSC, CLAT, NDA, CUET, BITSAT, etc.)
 * - Strict adherence to actual official examination patterns (e.g. JEE Main = 75 Qs / 300 Marks, NEET = 180 Qs / 720 Marks)
 * - Format toggle: Official Full-Length Paper vs. Rapid Sectional Practice
 * - Official Negative Marking & Palette Navigation
 * - AI Adaptive Practice Exam
 */
import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import Spinner from '../components/Spinner'
import { ENTRANCE_EXAMS, EXAM_CATEGORIES, EntranceExamPreset } from '../data/entranceExams'

interface Question {
  id: number
  domain: string
  skill: string
}

export default function ExamSetup() {
  const navigate = useNavigate()

  const [questions, setQuestions] = useState<Question[]>([])
  const [loadingQuestions, setLoadingQuestions] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  // Mode: 'live' (Standardized Entrance Exam) vs 'practice' (AI Adaptive)
  const [examType, setExamType] = useState<'live' | 'practice'>('live')

  // Selected Entrance Exam Preset (Default: JEE Main)
  const [selectedExamId, setSelectedExamId] = useState<string>('jee-main')
  const [selectedCategory, setSelectedCategory] = useState<string>('All')
  const [searchQuery, setSearchQuery] = useState('')

  // Format toggle: 'official' (exact official questions/marks) vs 'custom' (rapid sectional practice)
  const [testFormat, setTestFormat] = useState<'official' | 'custom'>('official')

  // Form state - initialized to JEE Main official pattern (75 Qs, 300 Marks, 180 Mins)
  const [customExamTitle, setCustomExamTitle] = useState('')
  const [domain, setDomain] = useState('Physics')
  const [skill, setSkill] = useState('')
  const [positiveMark, setPositiveMark] = useState(4.0)
  const [negativeMark, setNegativeMark] = useState(1.0)
  const [timeLimitMinutes, setTimeLimitMinutes] = useState(180)
  const [maxQuestions, setMaxQuestions] = useState(75)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Fetch questions from database to know what already exists
  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const res = await client.get('/questions')
        const data: Question[] = Array.isArray(res.data) ? res.data : res.data.questions ?? []
        setQuestions(data)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setFetchError(axiosErr.response?.data?.detail || 'Failed to load question catalogue.')
      } finally {
        setLoadingQuestions(false)
      }
    }
    fetchQuestions()
  }, [])

  // Currently selected preset
  const currentPreset = useMemo(
    () => ENTRANCE_EXAMS.find((e) => e.id === selectedExamId),
    [selectedExamId]
  )

  // Filtered exams by Category & Search
  const filteredExams = useMemo(() => {
    return ENTRANCE_EXAMS.filter((exam) => {
      const matchesCategory =
        selectedCategory === 'All' || exam.category === selectedCategory
      const matchesSearch =
        exam.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        exam.shortCode.toLowerCase().includes(searchQuery.toLowerCase()) ||
        exam.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        exam.defaultSubjects.some((s) => s.toLowerCase().includes(searchQuery.toLowerCase()))
      return matchesCategory && matchesSearch
    })
  }, [selectedCategory, searchQuery])

  // When a preset is chosen, auto-fill domain, marks, time, and official questions
  const handleSelectPreset = (preset: EntranceExamPreset) => {
    setSelectedExamId(preset.id)
    setPositiveMark(preset.positiveMark)
    setNegativeMark(preset.negativeMark)
    setTimeLimitMinutes(preset.defaultTimeMinutes)

    if (testFormat === 'official') {
      setMaxQuestions(preset.totalQuestions)
    } else {
      setMaxQuestions(Math.min(maxQuestions, preset.totalQuestions))
    }

    if (preset.defaultSubjects.length > 0) {
      setDomain(preset.defaultSubjects[0])
      setSkill('')
    }
  }

  // Handle format switch between Official Full-Length and Custom Rapid Practice
  const handleFormatChange = (format: 'official' | 'custom') => {
    setTestFormat(format)
    if (format === 'official' && currentPreset) {
      setMaxQuestions(currentPreset.totalQuestions)
      setTimeLimitMinutes(currentPreset.defaultTimeMinutes)
      setPositiveMark(currentPreset.positiveMark)
      setNegativeMark(currentPreset.negativeMark)
    }
  }

  // When user clicks a subject quick-pill
  const handleSelectSubjectPill = (subj: string) => {
    setDomain(subj)
    const matchingSkill = questions.find((q) => q.domain === subj)?.skill || ''
    setSkill(matchingSkill)
  }

  // Unique domains from existing DB questions
  const dbDomains = useMemo(
    () => [...new Set(questions.map((q) => q.domain))].filter(Boolean),
    [questions]
  )

  // Filter skills for selected domain if available in DB
  const availableSkills = useMemo(() => {
    return [
      ...new Set(questions.filter((q) => q.domain === domain).map((q) => q.skill)),
    ].filter(Boolean)
  }, [questions, domain])

  // Maximum allowable questions for current preset or custom
  const maxPossibleQuestions = useMemo(() => {
    return currentPreset ? Math.max(currentPreset.totalQuestions, 50) : 100
  }, [currentPreset])

  const calculatedTotalMarks = useMemo(() => {
    if (testFormat === 'official' && currentPreset && maxQuestions === currentPreset.totalQuestions) {
      return currentPreset.totalMarks
    }
    return Math.round(maxQuestions * positiveMark * 100) / 100
  }, [testFormat, currentPreset, maxQuestions, positiveMark])

  const handleStartExam = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)

    if (!domain.trim()) {
      setSubmitError('Please select or specify an exam subject / domain.')
      return
    }

    setSubmitting(true)
    const examTitle =
      selectedExamId === 'custom'
        ? customExamTitle.trim() || `${domain} Custom Entrance Exam`
        : currentPreset
        ? `${currentPreset.name} (${testFormat === 'official' ? 'Official Pattern' : 'Sectional Practice'}) - ${domain}`
        : `${domain} Entrance Exam`

    try {
      const res = await client.post('/exam-sessions', {
        domain: domain.trim(),
        skill: skill.trim() || undefined,
        max_questions: maxQuestions,
        exam_type: examType,
        positive_mark: positiveMark,
        negative_mark: negativeMark,
        exam_paper_title: examTitle,
        time_limit_seconds: examType === 'live' ? timeLimitMinutes * 60 : undefined,
      })
      const session = res.data
      navigate(`/exam/session/${session.id}`)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setSubmitError(axiosErr.response?.data?.detail || 'Failed to start exam session.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loadingQuestions) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-4 bg-red-50 border border-red-300 rounded-md">
        <p className="text-red-700">{fetchError}</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">National & Competitive Entrance Examination Portal</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Select an official competitive examination pattern (JEE 75 Qs / 300 Marks, NEET 180 Qs / 720 Marks, CAT 66 Qs / 198 Marks, etc.) or practice adaptively with our AI calibration engine.
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
        {submitError && (
          <div className="p-3 bg-red-50 border border-red-300 rounded-md">
            <p className="text-sm text-red-700 font-medium">{submitError}</p>
          </div>
        )}

        <form onSubmit={handleStartExam} className="space-y-6">
          {/* Mode Switch: Live Entrance vs Adaptive Practice */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
              Step 1: Choose Evaluation Mode
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                onClick={() => setExamType('live')}
                className={`cursor-pointer p-4 rounded-xl border-2 transition-all ${
                  examType === 'live'
                    ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">🏛️</span>
                    <div>
                      <h3 className="font-bold text-gray-900 text-sm">Standardized Live Entrance Exam</h3>
                      <p className="text-xs text-indigo-700 font-medium">Official Examination Pattern</p>
                    </div>
                  </div>
                  <span className="text-xs bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded-full">
                    Rank Evaluation
                  </span>
                </div>
                <p className="text-xs text-gray-600 mt-3 leading-relaxed">
                  • <strong>Exact Exam Blueprint:</strong> Official question counts, total marks & time limits.<br />
                  • <strong>Identical Paper:</strong> Fixed questions served in standard exam sequence.<br />
                  • <strong>Question Palette:</strong> Mark for Review, Save & Next, Clear Response.<br />
                  • <strong>Zero Spoilers:</strong> Detailed solutions revealed only after final submission.
                </p>
              </div>

              <div
                onClick={() => setExamType('practice')}
                className={`cursor-pointer p-4 rounded-xl border-2 transition-all ${
                  examType === 'practice'
                    ? 'border-blue-600 bg-blue-50/50 shadow-sm'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">🧠</span>
                    <div>
                      <h3 className="font-bold text-gray-900 text-sm">AI Adaptive Practice Exam</h3>
                      <p className="text-xs text-blue-700 font-medium">Diagnostic & Mastery Training</p>
                    </div>
                  </div>
                  <span className="text-xs bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full">
                    AI Powered
                  </span>
                </div>
                <p className="text-xs text-gray-600 mt-3 leading-relaxed">
                  • <strong>Dynamic Difficulty:</strong> Calibrated using Thompson Sampling Bandit.<br />
                  • <strong>Instant Feedback:</strong> Deep step-by-step conceptual explanations per question.<br />
                  • <strong>Generative AI:</strong> High-speed question synthesis via Groq Cloud LLM.<br />
                  • <strong>IRT Analytics:</strong> Real-time student ability (theta) & mastery tracking.
                </p>
              </div>
            </div>
          </div>

          <hr className="border-gray-100" />

          {/* Step 2: Choose Entrance Examination */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-500">
                  Step 2: Select Entrance Examination Pattern
                </label>
                <p className="text-xs text-gray-400">
                  Choose from {ENTRANCE_EXAMS.length}+ competitive entrance exams across disciplines.
                </p>
              </div>

              {/* Search bar */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search exam (e.g. JEE, NEET, CAT, UPSC)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="px-3 py-1.5 pl-8 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 w-60"
                />
                <span className="absolute left-2.5 top-2 text-gray-400 text-xs">🔍</span>
              </div>
            </div>

            {/* Category Filter Pills */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {EXAM_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                    selectedCategory === cat
                      ? 'bg-gray-900 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Exam Presets Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-80 overflow-y-auto p-1 border border-gray-100 rounded-xl bg-gray-50/50">
              {filteredExams.map((exam) => {
                const isSelected = selectedExamId === exam.id
                return (
                  <div
                    key={exam.id}
                    onClick={() => handleSelectPreset(exam)}
                    className={`cursor-pointer p-3 rounded-lg border transition-all text-left flex flex-col justify-between ${
                      isSelected
                        ? 'border-indigo-600 bg-white shadow-sm ring-2 ring-indigo-500/20'
                        : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-xs'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="text-lg">{exam.icon}</span>
                          <span className="font-bold text-xs text-gray-900 truncate">
                            {exam.shortCode}
                          </span>
                        </div>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 shrink-0">
                          {exam.totalQuestions} Qs • {exam.totalMarks} M
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-600 font-medium line-clamp-1">{exam.name}</p>
                      <p className="text-[10px] text-gray-400 mt-1 line-clamp-2">{exam.description}</p>
                    </div>

                    <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-500">
                      <span className="font-mono text-gray-600">+{exam.positiveMark} / -{exam.negativeMark}</span>
                      <span className="font-medium text-indigo-600">{exam.defaultTimeMinutes} min</span>
                    </div>
                  </div>
                )
              })}

              {/* Custom Exam Option */}
              <div
                onClick={() => {
                  setSelectedExamId('custom')
                  setPositiveMark(4.0)
                  setNegativeMark(1.0)
                  setTimeLimitMinutes(60)
                  setMaxQuestions(25)
                }}
                className={`cursor-pointer p-3 rounded-lg border-2 border-dashed transition-all text-left flex flex-col justify-center items-center text-center ${
                  selectedExamId === 'custom'
                    ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/20'
                    : 'border-gray-300 bg-white hover:border-gray-400'
                }`}
              >
                <span className="text-2xl">✨</span>
                <span className="font-bold text-xs text-gray-900 mt-1">Other / Custom Exam</span>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  Configure custom question counts and scoring marks.
                </p>
              </div>
            </div>
          </div>

          {/* Custom Exam Name (Only if custom is chosen) */}
          {selectedExamId === 'custom' && (
            <div className="p-4 bg-indigo-50/60 border border-indigo-200 rounded-xl space-y-3">
              <label className="block text-xs font-bold text-indigo-900 uppercase">
                Custom Exam Details
              </label>
              <input
                type="text"
                placeholder="Enter Examination Name (e.g., ISRO Scientist Exam, BARC OCES, Cambridge Tripos)..."
                value={customExamTitle}
                onChange={(e) => setCustomExamTitle(e.target.value)}
                className="w-full px-3 py-2 border border-indigo-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Official Pattern Summary Banner */}
          {currentPreset && (
            <div className="p-3 bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-200 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-xl">{currentPreset.icon}</span>
                <div>
                  <span className="font-bold text-indigo-950 text-sm">{currentPreset.name}</span>
                  <p className="text-indigo-700 text-[11px]">
                    Official Pattern: <strong>{currentPreset.totalQuestions} Questions</strong> •{' '}
                    <strong>{currentPreset.totalMarks} Marks</strong> •{' '}
                    <strong>{currentPreset.defaultTimeMinutes} Minutes</strong> • Marking: (+{currentPreset.positiveMark} / -{currentPreset.negativeMark})
                  </p>
                </div>
              </div>

              {/* Format Switcher */}
              <div className="flex items-center bg-white p-1 rounded-lg border border-indigo-200 shadow-xs">
                <button
                  type="button"
                  onClick={() => handleFormatChange('official')}
                  className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                    testFormat === 'official'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  📋 Official Full Paper ({currentPreset.totalQuestions} Qs)
                </button>
                <button
                  type="button"
                  onClick={() => handleFormatChange('custom')}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    testFormat === 'custom'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  ⚡ Rapid / Sectional Practice
                </button>
              </div>
            </div>
          )}

          <hr className="border-gray-100" />

          {/* Step 3: Subject / Domain Selection */}
          <div className="space-y-3">
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-500">
              Step 3: Subject & Topic Configuration
            </label>

            {/* Quick-Pick Subject Pills from Current Preset */}
            {currentPreset && currentPreset.defaultSubjects.length > 0 && (
              <div>
                <span className="text-xs text-gray-500 font-medium mr-2">Standard Exam Subjects:</span>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {currentPreset.defaultSubjects.map((subj) => (
                    <button
                      key={subj}
                      type="button"
                      onClick={() => handleSelectSubjectPill(subj)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                        domain === subj
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
                      }`}
                    >
                      {subj}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Domain / Subject Input or Dropdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Active Exam Subject / Domain
                </label>
                <input
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="e.g. Physics, Quantitative Aptitude, Indian Polity"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
                {dbDomains.length > 0 && (
                  <p className="text-[10px] text-gray-400 mt-1">
                    Existing Catalogue: {dbDomains.slice(0, 4).join(', ')}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Topic / Sub-skill <span className="text-gray-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  value={skill}
                  onChange={(e) => setSkill(e.target.value)}
                  placeholder="e.g. Thermodynamics, Calculus, Modern History, All Topics"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                {availableSkills.length > 0 && (
                  <p className="text-[10px] text-gray-400 mt-1">
                    Available: {availableSkills.slice(0, 3).join(', ')}
                  </p>
                )}
              </div>
            </div>
          </div>

          <hr className="border-gray-100" />

          {/* Step 4: Marking Scheme & Time Limits */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-500">
                Step 4: Examination Constraints & Scoring Rules
              </label>
              {currentPreset && testFormat === 'official' && (
                <span className="text-xs text-green-700 bg-green-50 px-2 py-0.5 rounded font-bold border border-green-200">
                  ✓ Official Pattern Locked
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Positive Mark */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Marks per Correct Answer
                </label>
                <div className="flex items-center">
                  <span className="px-2.5 py-2 bg-gray-100 border border-r-0 border-gray-300 rounded-l-lg text-xs font-bold text-green-700">
                    +
                  </span>
                  <input
                    type="number"
                    step="0.25"
                    min="0.5"
                    max="10"
                    value={positiveMark}
                    onChange={(e) => setPositiveMark(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-r-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>

              {/* Negative Mark */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Penalty per Wrong Answer
                </label>
                <div className="flex items-center">
                  <span className="px-2.5 py-2 bg-gray-100 border border-r-0 border-gray-300 rounded-l-lg text-xs font-bold text-red-700">
                    -
                  </span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="5"
                    value={negativeMark}
                    onChange={(e) => setNegativeMark(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-r-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>

              {/* Time limit (for live mocks) */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Exam Timer Duration
                </label>
                <div className="flex items-center">
                  <input
                    type="number"
                    min="5"
                    max="360"
                    step="5"
                    value={timeLimitMinutes}
                    onChange={(e) => setTimeLimitMinutes(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-l-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                  <span className="px-2.5 py-2 bg-gray-100 border border-l-0 border-gray-300 rounded-r-lg text-xs font-medium text-gray-600">
                    min
                  </span>
                </div>
              </div>
            </div>

            {/* Questions count slider & quick buttons */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-medium text-gray-700">
                  Number of Test Questions
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-extrabold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    {maxQuestions} Questions
                  </span>
                  <span className="text-xs font-bold text-gray-500">
                    ({calculatedTotalMarks} Total Marks)
                  </span>
                </div>
              </div>

              {/* Quick Preset Pills for Questions */}
              <div className="flex flex-wrap items-center gap-2 mb-2">
                {currentPreset && (
                  <button
                    type="button"
                    onClick={() => {
                      setMaxQuestions(currentPreset.totalQuestions)
                      setTestFormat('official')
                    }}
                    className={`px-2.5 py-1 text-xs rounded-md font-bold border transition-all ${
                      maxQuestions === currentPreset.totalQuestions
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                        : 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
                    }`}
                  >
                    ⭐ Official Full Paper ({currentPreset.totalQuestions} Qs)
                  </button>
                )}
                {[10, 25, 50].map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => {
                      setMaxQuestions(count)
                      setTestFormat('custom')
                    }}
                    className={`px-2.5 py-1 text-xs rounded-md font-medium border transition-all ${
                      maxQuestions === count && testFormat === 'custom'
                        ? 'bg-gray-800 text-white border-gray-800'
                        : 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200'
                    }`}
                  >
                    {count} Qs
                  </button>
                ))}
              </div>

              <input
                type="range"
                min={5}
                max={maxPossibleQuestions}
                step={5}
                value={maxQuestions}
                onChange={(e) => {
                  setMaxQuestions(Number(e.target.value))
                  if (currentPreset && Number(e.target.value) !== currentPreset.totalQuestions) {
                    setTestFormat('custom')
                  }
                }}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                <span>5 (Mini Test)</span>
                <span>25 (Standard Practice)</span>
                <span>50 (Sectional)</span>
                <span>{maxPossibleQuestions} (Full Official)</span>
              </div>
            </div>
          </div>

          {/* Active Marking Scheme Banner */}
          {examType === 'live' && (
            <div className="p-3 bg-indigo-900 text-white rounded-xl text-xs flex flex-wrap items-center justify-between gap-2 shadow">
              <div className="flex items-center gap-2">
                <span className="text-lg">⚖️</span>
                <span>
                  <strong>Official Scoring Active:</strong> +{positiveMark} for correct, -{negativeMark} for incorrect, 0 for unattempted.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="bg-indigo-800 px-2.5 py-1 rounded-md text-[11px] font-mono text-indigo-200">
                  Questions: {maxQuestions}
                </span>
                <span className="bg-indigo-700 px-2.5 py-1 rounded-md text-[11px] font-mono text-white font-bold">
                  Total Marks: {calculatedTotalMarks}
                </span>
              </div>
            </div>
          )}

          {/* Submit Action */}
          <button
            type="submit"
            disabled={submitting || !domain.trim()}
            className={`w-full py-3.5 px-4 text-white font-bold rounded-xl shadow-md text-sm transition-all transform active:scale-[0.99] ${
              examType === 'live'
                ? 'bg-gradient-to-r from-indigo-600 to-indigo-800 hover:from-indigo-700 hover:to-indigo-900'
                : 'bg-gradient-to-r from-blue-600 to-blue-800 hover:from-blue-700 hover:to-blue-900'
            } disabled:opacity-50`}
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner size="sm" /> Preparing Standardized Exam Paper...
              </span>
            ) : examType === 'live' ? (
              `Start ${currentPreset?.shortCode || 'Live Entrance'} Exam (${maxQuestions} Questions • ${calculatedTotalMarks} Marks • ${timeLimitMinutes} Mins)`
            ) : (
              `Start AI Adaptive Practice Session (${maxQuestions} Questions • ${calculatedTotalMarks} Marks)`
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
