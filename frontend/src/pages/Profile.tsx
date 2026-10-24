/**
 * pages/Profile.tsx
 * User profile page - shows name, email, and role from GET /me.
 * Provides a logout button for convenience.
 */
import React, { useEffect, useState } from 'react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/Spinner'

interface UserProfile {
  id: number
  name: string
  email: string
  role: string
  created_at?: string
}

export default function Profile() {
  const { logout } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await client.get('/me')
        setProfile(res.data)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(axiosErr.response?.data?.detail || 'Failed to load profile.')
      } finally {
        setLoading(false)
      }
    }
    fetchProfile()
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="p-4 bg-red-50 border border-red-300 rounded-md">
        <p className="text-red-700">{error || 'Profile not available.'}</p>
      </div>
    )
  }

  const joinDate = profile.created_at
    ? new Date(profile.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>

      {/* Profile card */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Avatar placeholder */}
        <div className="flex items-center gap-5 mb-6">
          <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center text-white text-2xl font-bold select-none">
            {profile.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">{profile.name}</h2>
            <span
              className={`inline-block mt-1 px-3 py-0.5 rounded-full text-xs font-medium uppercase tracking-wide ${
                profile.role === 'admin'
                  ? 'bg-purple-100 text-purple-700'
                  : profile.role === 'reviewer'
                  ? 'bg-orange-100 text-orange-700'
                  : 'bg-blue-100 text-blue-700'
              }`}
            >
              {profile.role}
            </span>
          </div>
        </div>

        {/* Details */}
        <dl className="space-y-4">
          <ProfileField label="Full Name" value={profile.name} />
          <ProfileField label="Email Address" value={profile.email} />
          <ProfileField label="Account Role" value={profile.role} />
          <ProfileField label="User ID" value={`#${profile.id}`} />
          {joinDate && <ProfileField label="Member Since" value={joinDate} />}
        </dl>
      </div>

      {/* Sign out */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-base font-semibold text-gray-800 mb-3">Account Actions</h3>
        <button
          onClick={logout}
          className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 transition-colors"
        >
          Sign Out
        </button>
      </div>
    </div>
  )
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
      <dt className="w-40 text-sm font-medium text-gray-500 flex-shrink-0">{label}</dt>
      <dd className="text-sm text-gray-900">{value}</dd>
    </div>
  )
}
