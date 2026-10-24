/**
 * components/Spinner.tsx
 * Reusable loading spinner shown during API requests.
 * Accepts an optional size prop (default: medium).
 */
import React from 'react'

interface Props {
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-4',
}

export default function Spinner({ size = 'md' }: Props) {
  return (
    <div
      className={`${sizeClasses[size]} rounded-full border-gray-300 border-t-blue-600 animate-spin inline-block`}
      role="status"
      aria-label="Loading"
    />
  )
}
