/**
 * components/Layout.tsx
 * Main application shell with top navigation bar.
 * Navigation links are role-aware:
 * - All authenticated users see: Dashboard, Exam, History, Profile
 * - Admin users additionally see: Admin
 * - Admin and Reviewer users see: Reviewer
 * Logout button clears session and redirects to /login.
 */
import React from 'react'
import { Link, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import AIAssistantWidget from './AIAssistantWidget'

export default function Layout() {
  const { user, logout, isAdmin, isReviewer } = useAuth()
  const location = useLocation()

  // Helper to highlight the active nav link
  const isActive = (path: string) =>
    location.pathname.startsWith(path)
      ? 'bg-blue-700 text-white'
      : 'text-gray-300 hover:bg-gray-700 hover:text-white'

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Top navigation bar */}
      <nav className="bg-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Brand */}
            <div className="flex items-center">
              <Link to="/dashboard" className="text-white font-bold text-lg tracking-wide">
                Exam Portal
              </Link>

              {/* Primary navigation links */}
              <div className="ml-10 flex items-baseline space-x-2">
                <Link
                  to="/dashboard"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/dashboard')}`}
                >
                  Dashboard
                </Link>
                <Link
                  to="/exam/setup"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/exam')}`}
                >
                  Exam
                </Link>
                <Link
                  to="/history"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/history')}`}
                >
                  History
                </Link>
                <Link
                  to="/profile"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/profile')}`}
                >
                  Profile
                </Link>

                {/* Admin-only link */}
                {isAdmin() && (
                  <Link
                    to="/admin"
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/admin')}`}
                  >
                    Admin
                  </Link>
                )}

                {/* Reviewer link (admin and reviewer roles) */}
                {isReviewer() && (
                  <Link
                    to="/reviewer"
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive('/reviewer')}`}
                  >
                    Reviewer
                  </Link>
                )}
              </div>
            </div>

            {/* Right side: user info and logout */}
            <div className="flex items-center space-x-4">
              <span className="text-gray-300 text-sm">
                {user?.name}
                <span className="ml-2 px-2 py-0.5 bg-gray-600 rounded text-xs uppercase tracking-wide">
                  {user?.role}
                </span>
              </span>
              <button
                onClick={logout}
                className="px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Page content rendered here */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Omnipresent AI Assistant, Doubt Solver & Exam Integrity Monitor */}
      <AIAssistantWidget />
    </div>
  )
}
