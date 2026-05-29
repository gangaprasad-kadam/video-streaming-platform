import { useState, useEffect, useCallback } from 'react'
import { getVideoStatus } from '@/api/videos'

const POLL_INTERVAL = 3000
const TERMINAL = new Set(['ready', 'failed'])

export default function useVideoStatus(videoId, initialStatus = 'uploading') {
  const [status, setStatus] = useState(initialStatus)
  const [error,  setError]  = useState(null)

  const poll = useCallback(() => {
    if (!videoId || TERMINAL.has(status)) return
    getVideoStatus(videoId)
      .then((res) => {
        const s = res?.status ?? res
        setStatus(s)
      })
      .catch((e) => setError(e.message))
  }, [videoId, status])

  useEffect(() => {
    if (!videoId || TERMINAL.has(status)) return
    const id = setInterval(poll, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [videoId, status, poll])

  return { status, error }
}
