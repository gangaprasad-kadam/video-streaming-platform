import { useEffect, useRef } from 'react'
import Hls from 'hls.js'

export default function HlsPlayer({ src, onTimeUpdate, onPlay, onPause, onSeeked, videoRef: externalRef }) {
  const internalRef = useRef(null)
  const videoRef = externalRef || internalRef
  const hlsRef = useRef(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !src) return

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true, lowLatencyMode: false })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
      return () => { hls.destroy(); hlsRef.current = null }
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      video.src = src
    }
  }, [src, videoRef])

  return (
    <video
      ref={videoRef}
      controls
      style={{ width: '100%', height: 'auto', display: 'block', background: '#000', borderRadius: '8px' }}
      onTimeUpdate={onTimeUpdate}
      onPlay={onPlay}
      onPause={onPause}
      onSeeked={onSeeked}
      aria-label="Video player"
    />
  )
}
