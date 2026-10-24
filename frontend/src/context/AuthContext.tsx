/**
 * context/AuthContext.tsx
 * Global authentication context providing:
 * - Current user data (id, name, email, role)
 * - Login function: calls POST /login, stores token + user in localStorage
 * - Logout function: clears all stored data and redirects to /login
 * - isAuthenticated flag and role-check helpers
 *
 * Wrap the app with <AuthProvider> so any component can call useAuth().
 */
import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import client from '../api/client'

// Shape of the user object returned by GET /me
export interface User {
  id: number
  name: string
  email: string
  role: 'student' | 'admin' | 'reviewer'
}

interface AuthContextValue {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAdmin: () => boolean
  isReviewer: () => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  // Initialize from localStorage so state persists across page refreshes
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

  /**
   * login: authenticates with the backend, then fetches the user profile
   * to get role information. Stores both token and user in localStorage.
   */
  const login = useCallback(async (email: string, password: string) => {
    const response = await client.post('/login', { email, password })
    const { access_token } = response.data

    // Store token first so the /me request includes it
    localStorage.setItem('token', access_token)
    setToken(access_token)

    // Fetch full user profile (includes role)
    const meResponse = await client.get('/me')
    const userData: User = meResponse.data

    localStorage.setItem('user', JSON.stringify(userData))
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
    window.location.href = '/login'
  }, [])

  const isAdmin = useCallback(() => user?.role === 'admin', [user])
  const isReviewer = useCallback(() => user?.role === 'reviewer' || user?.role === 'admin', [user])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        login,
        logout,
        isAdmin,
        isReviewer,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

/** Hook to access auth context. Must be used inside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
