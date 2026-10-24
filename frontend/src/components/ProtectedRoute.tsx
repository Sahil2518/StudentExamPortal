/**
 * components/ProtectedRoute.tsx
 * Guards routes that require authentication or specific roles.
 *
 * Usage patterns:
 *  1. Wrapping the entire Layout (no role check):
 *     <ProtectedRoute><Layout /></ProtectedRoute>
 *
 *  2. Wrapping a specific page (with role check):
 *     <ProtectedRoute requireAdmin><AdminDashboard /></ProtectedRoute>
 *
 * If not authenticated: redirects to /login
 * If role check fails: shows Access Denied message
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

interface Props {
  children: React.ReactNode
  requireAdmin?: boolean
  requireReviewer?: boolean
}

export default function ProtectedRoute({ children, requireAdmin, requireReviewer }: Props) {
  const { isAuthenticated, isAdmin, isReviewer } = useAuth()

  // Not logged in at all
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Admin-only page check
  if (requireAdmin && !isAdmin()) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800">Access Denied</h2>
          <p className="text-gray-500 mt-2">This page requires administrator access.</p>
        </div>
      </div>
    )
  }

  // Reviewer-or-admin page check
  if (requireReviewer && !isReviewer()) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-800">Access Denied</h2>
          <p className="text-gray-500 mt-2">This page requires reviewer or admin access.</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
