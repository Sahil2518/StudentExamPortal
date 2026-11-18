/**
 * hooks/useFaceDetection.ts
 * AI-powered face detection using face-api.js (TensorFlow.js under the hood).
 * Uses the lightweight TinyFaceDetector model (~190KB).
 *
 * Detects:
 *  - No face (student looked away / left seat)
 *  - Multiple faces (someone else present / helping)
 *
 * Runs every 3 seconds in the background while exam is active.
 */
import { useEffect, useRef, useState, useCallback } from 'react'

// Lazy-load face-api to avoid blocking the main bundle
let faceapi: typeof import('face-api.js') | null = null

// CDN for model weights (tiny face detector — ~190KB, fastest model)
const MODEL_URL = 'https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights'

// How many consecutive "no face" checks before triggering violation (3s × 2 = 6s)
const NO_FACE_THRESHOLD = 2

export type FaceStatus = 'loading' | 'ready' | 'face_ok' | 'no_face' | 'multiple_faces' | 'error'

export function useFaceDetection(
  videoRef: React.RefObject<HTMLVideoElement>,
  onNoFace: () => void,
  onMultipleFaces: () => void,
  enabled: boolean = true
) {
  const [status, setStatus] = useState<FaceStatus>('loading')
  const [faceCount, setFaceCount] = useState<number | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const noFaceCountRef = useRef(0)
  const modelLoadedRef = useRef(false)

  // Stable callbacks via refs to avoid re-triggering effects
  const onNoFaceRef = useRef(onNoFace)
  const onMultipleFacesRef = useRef(onMultipleFaces)
  useEffect(() => { onNoFaceRef.current = onNoFace }, [onNoFace])
  useEffect(() => { onMultipleFacesRef.current = onMultipleFaces }, [onMultipleFaces])

  // Load face-api model
  useEffect(() => {
    if (!enabled) return
    let cancelled = false

    const loadModel = async () => {
      try {
        // Lazy-load the library
        if (!faceapi) {
          faceapi = await import('face-api.js')
        }

        if (!modelLoadedRef.current) {
          await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL)
          modelLoadedRef.current = true
        }

        if (!cancelled) setStatus('ready')
      } catch (err) {
        console.error('[FaceDetection] Failed to load model:', err)
        if (!cancelled) setStatus('error')
      }
    }

    loadModel()
    return () => { cancelled = true }
  }, [enabled])

  // Run detection loop
  useEffect(() => {
    if (status !== 'ready' && status !== 'face_ok' && status !== 'no_face' && status !== 'multiple_faces') return
    if (!enabled || !faceapi) return

    const detect = async () => {
      const video = videoRef.current
      if (!video || video.readyState < 2 || video.paused || video.ended) return
      if (!faceapi) return

      try {
        const detections = await faceapi.detectAllFaces(
          video,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 160, scoreThreshold: 0.5 })
        )

        const count = detections.length
        setFaceCount(count)

        if (count === 0) {
          noFaceCountRef.current += 1
          setStatus('no_face')
          if (noFaceCountRef.current >= NO_FACE_THRESHOLD) {
            noFaceCountRef.current = 0
            onNoFaceRef.current()
          }
        } else if (count > 1) {
          noFaceCountRef.current = 0
          setStatus('multiple_faces')
          onMultipleFacesRef.current()
        } else {
          noFaceCountRef.current = 0
          setStatus('face_ok')
        }
      } catch {
        // Silent fail — don't trigger violations on detection errors
      }
    }

    // Initial detection after a short delay (let video stabilize)
    const initialDelay = setTimeout(detect, 2000)
    intervalRef.current = setInterval(detect, 3000)

    return () => {
      clearTimeout(initialDelay)
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [status, enabled, videoRef])

  return { status, faceCount }
}
