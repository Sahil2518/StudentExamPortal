import { useEffect, useRef, useState, useCallback } from 'react'
import client from '../api/client'
import { v4 as uuidv4 } from 'uuid'

export function useCameraProctoring(examSessionId: string | undefined) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [hasPermission, setHasPermission] = useState<boolean>(false)
  const sequenceNumberRef = useRef(1)

  const sendEvent = useCallback(
    async (eventType: string, severity: string, confidence: number = 1.0, metadata?: Record<string, unknown>) => {
      if (!examSessionId) return
      
      const payload = {
        exam_session_id: examSessionId,
        client_event_id: uuidv4(),
        sequence_number: sequenceNumberRef.current++,
        event_type: eventType,
        severity: severity,
        confidence: confidence,
        event_metadata: metadata || {}
      }
      
      try {
        await client.post('/proctoring-events', payload)
      } catch (err) {
        console.error('Failed to send proctoring event', err)
      }
    },
    [examSessionId]
  )

  useEffect(() => {
    let mounted = true

    const initCamera = async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError('Camera API not supported in this browser.')
        if (examSessionId) sendEvent('camera_blocked', 'high')
        return
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        if (!mounted) {
          stream.getTracks().forEach(track => track.stop())
          return
        }
        
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
        setHasPermission(true)
        setCameraError(null)
      } catch (err) {
        console.error('Camera permission denied or error', err)
        if (mounted) {
          setCameraError('Camera access denied. Please allow camera permissions.')
          setHasPermission(false)
          if (examSessionId) sendEvent('camera_blocked', 'high')
        }
      }
    }

    initCamera()

    return () => {
      mounted = false
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
    }
  }, [examSessionId, sendEvent])

  return {
    videoRef,
    cameraError,
    hasPermission,
    sendEvent
  }
}
