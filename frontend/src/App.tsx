/**
 * App.tsx
 * Root component - sets up React Router v6 routes with role-based guards.
 *
 * Route structure:
 *   /login                    - public
 *   /register                 - public
 *   /                         - redirects to /dashboard
 *   /dashboard                - authenticated (any role)
 *   /exam/setup               - authenticated
 *   /exam/session/:sessionId  - authenticated
 *   /exam/results/:sessionId  - authenticated
 *   /history                  - authenticated
 *   /profile                  - authenticated
 *   /admin                    - admin only
 *   /reviewer                 - reviewer or admin
 *
 * ProtectedLayout (outer) handles auth check and renders Layout + Outlet.
 * RoleGuard (inner) handles role-specific page restrictions.
 */
import React, { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedLayout from './components/ProtectedLayout'
import Spinner from './components/Spinner'

// Lazy load pages for fast initial page load and bundle splitting
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ExamSetup = lazy(() => import('./pages/ExamSetup'))
const ExamSession = lazy(() => import('./pages/ExamSession'))
const ExamResults = lazy(() => import('./pages/ExamResults'))
const History = lazy(() => import('./pages/History'))
const Profile = lazy(() => import('./pages/Profile'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const ReviewerDashboard = lazy(() => import('./pages/ReviewerDashboard'))

function PageFallback() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
}

// ---- Role gate components ----

/** Renders children only if user is an admin, otherwise shows Access Denied */
function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useAuth()
  if (!isAdmin()) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800">Access Denied</h2>
          <p className="text-gray-500 mt-2">Administrator access is required for this page.</p>
        </div>
      </div>
    )
  }
  return <>{children}</>
}

/** Renders children only if user is admin or reviewer, otherwise shows Access Denied */
function RequireReviewer({ children }: { children: React.ReactNode }) {
  const { isReviewer } = useAuth()
  if (!isReviewer()) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800">Access Denied</h2>
          <p className="text-gray-500 mt-2">Reviewer or admin access is required for this page.</p>
        </div>
      </div>
    )
  }
  return <>{children}</>
}

// ---- App ----

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />

            {/* Root: redirect to dashboard */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            {/*
             * Protected routes: ProtectedLayout checks isAuthenticated,
             * redirects to /login if not, otherwise renders Layout (nav + Outlet).
             */}
            <Route element={<ProtectedLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/exam/setup" element={<ExamSetup />} />
              <Route path="/exam/session/:sessionId" element={<ExamSession />} />
              <Route path="/exam/results/:sessionId" element={<ExamResults />} />
              <Route path="/history" element={<History />} />
              <Route path="/profile" element={<Profile />} />

              {/* Admin-only page */}
              <Route
                path="/admin"
                element={
                  <RequireAdmin>
                    <AdminDashboard />
                  </RequireAdmin>
                }
              />

              {/* Reviewer (and admin) page */}
              <Route
                path="/reviewer"
                element={
                  <RequireReviewer>
                    <ReviewerDashboard />
                  </RequireReviewer>
                }
              />
            </Route>

            {/* Catch-all fallback */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}
