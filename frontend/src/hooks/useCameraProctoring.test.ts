import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCameraProctoring } from './useCameraProctoring'
import client from '../api/client'

// Mock the API client
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

// Mock uuid
vi.mock('uuid', () => ({
  v4: () => 'fake-uuid-1234',
}))

describe('useCameraProctoring', () => {
  let mockGetUserMedia: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockGetUserMedia = vi.fn()
    
    // Setup navigator.mediaDevices mock
    Object.defineProperty(globalThis.navigator, 'mediaDevices', {
      value: {
        getUserMedia: mockGetUserMedia,
      },
      writable: true,
      configurable: true,
    })
    
    vi.clearAllMocks()
  })
  
  afterEach(() => {
    // Clean up mock
    Object.defineProperty(globalThis.navigator, 'mediaDevices', {
      value: undefined,
      writable: true,
      configurable: true,
    })
  })

  it('initializes successfully when permission granted', async () => {
    // Mock a successful stream
    const mockTrack = { stop: vi.fn() }
    const mockStream = { getTracks: () => [mockTrack] }
    mockGetUserMedia.mockResolvedValue(mockStream)

    const { result, unmount } = renderHook(() => useCameraProctoring('session-123'))

    // Wait for async initialization
    await vi.waitFor(() => {
      expect(result.current.hasPermission).toBe(true)
    })

    expect(result.current.cameraError).toBeNull()
    expect(mockGetUserMedia).toHaveBeenCalledWith({ video: true, audio: false })

    // Verify cleanup
    unmount()
    expect(mockTrack.stop).toHaveBeenCalled()
  })

  it('handles permission denied properly and sends proctoring event', async () => {
    // Mock permission denied
    mockGetUserMedia.mockRejectedValue(new Error('NotAllowedError'))

    const { result } = renderHook(() => useCameraProctoring('session-123'))

    await vi.waitFor(() => {
      expect(result.current.cameraError).toContain('Camera access denied')
    })

    expect(result.current.hasPermission).toBe(false)
    
    // It should have sent a "camera_blocked" event
    expect(client.post).toHaveBeenCalledWith('/proctoring-events', expect.objectContaining({
      event_type: 'camera_blocked',
      severity: 'high',
      exam_session_id: 'session-123'
    }))
  })

  it('handles missing mediaDevices support', async () => {
    // Remove mediaDevices entirely
    Object.defineProperty(globalThis.navigator, 'mediaDevices', {
      value: undefined,
      writable: true,
    })

    const { result } = renderHook(() => useCameraProctoring('session-123'))

    // Synchronously sets error
    expect(result.current.cameraError).toContain('Camera API not supported')
    expect(result.current.hasPermission).toBe(false)
    
    // It should have sent a "camera_blocked" event
    expect(client.post).toHaveBeenCalledWith('/proctoring-events', expect.objectContaining({
      event_type: 'camera_blocked',
      severity: 'high',
      exam_session_id: 'session-123'
    }))
  })
})
