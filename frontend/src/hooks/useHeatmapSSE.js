import { useState, useEffect, useRef } from 'react'
import { getHeatmapStreamUrl } from '@/api/heatmap'

export default function useHeatmapSSE(videoId) {
  const [data,  setData]  = useState(null)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!videoId) return

    const connect = () => {
      const es = new EventSource(getHeatmapStreamUrl(videoId), { withCredentials: true })
      esRef.current = es

      es.onmessage = (e) => {
        try { setData(JSON.parse(e.data)) } catch { /* skip malformed */ }
      }

      es.onerror = () => {
        setError('Connection lost, retrying…')
        es.close()
        // Reconnect after 3s
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => { esRef.current?.close() }
  }, [videoId])

  return { data, error }
}
