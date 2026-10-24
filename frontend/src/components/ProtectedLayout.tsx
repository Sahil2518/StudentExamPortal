/**
 * components/ProtectedLayout.tsx
 * Checks authentication and renders the Layout with Outlet for nested routes.
 * If the user is not authenticated, redirects to /login.
 * This is the outer shell for all authenticated routes.
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Layout from './Layout'

export default function ProtectedLayout() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Layout renders the nav bar; child routes appear via <Outlet /> inside Layout
  return <Layout />
}
