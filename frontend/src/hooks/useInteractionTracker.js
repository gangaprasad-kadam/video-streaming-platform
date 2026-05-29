import { useRef, useEffect, useCallback } from 'react'
import { postInteraction } from '@/api/events'

export default function useInteractionTracker(videoId, userId = '') {
  const buffer   = useRef([])
  const prevTime = useRef(0)
  const timerRef = useRef(null)

  const flush = useCallback(() => {
    if (!buffer.current.length) return
    const events = [...buffer.current]
    buffer.current = []
    events.forEach((ev) => postInteraction(ev).catch(() => {}))
  }, [])

  // Flush every 3 seconds
  useEffect(() => {
    timerRef.current = setInterval(flush, 3000)
    return () => { clearInterval(timerRef.current); flush() }
  }, [flush])

  const track = useCallback((action, videoTs) => {
    if (!videoId) return
    // Payload matches backend InteractionEventRequest (camelCase fields)
    buffer.current.push({
      userId:  userId || 'anonymous',
      videoId: videoId,
      action:  action,
      videoTs: videoTs,
    })
  }, [videoId, userId])

  const onPlay    = useCallback((e) => track('PLAY',  e.target.currentTime), [track])
  const onPause   = useCallback((e) => track('PAUSE', e.target.currentTime), [track])
  const onSeeked  = useCallback((e) => {
    const newTime = e.target.currentTime
    const type    = newTime < prevTime.current ? 'REWIND' : 'SEEK'
    prevTime.current = newTime
    track(type, newTime)
  }, [track])
  const onTimeUpdate = useCallback((e) => {
    prevTime.current = e.target.currentTime
  }, [])

  return { onPlay, onPause, onSeeked, onTimeUpdate }
}
