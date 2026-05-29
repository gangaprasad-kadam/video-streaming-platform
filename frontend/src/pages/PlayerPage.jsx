import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { getVideo } from '@/api/videos'
import { getManifestUrl } from '@/api/stream'
import HlsPlayer from '@/components/HlsPlayer'
import SummaryPanel from '@/components/SummaryPanel'
import HeatmapChart from '@/components/HeatmapChart'
import useInteractionTracker from '@/hooks/useInteractionTracker'
import s from './PlayerPage.module.css'

export default function PlayerPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [video,   setVideo]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const videoRef = useRef(null)

  const { onPlay, onPause, onSeeked, onTimeUpdate } = useInteractionTracker(id, user?.id)

  useEffect(() => {
    setLoading(true)
    getVideo(id)
      .then(setVideo)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const seekTo = (time) => {
    if (videoRef.current) videoRef.current.currentTime = time
  }

  if (loading) return (
    <div className={s.loadingBox}><span className="spinner" /> Loading video…</div>
  )
  if (error) return (
    <div className="container" style={{ padding: 'var(--space-8) 0' }}>
      <div className="alert alert-error">{error}</div>
    </div>
  )
  if (!video) return null

  return (
    <div className={s.page}>
      <div className="container">
        <div className={s.layout}>
          {/* Main player column */}
          <div>
            <div className={s.playerWrap}>
              <HlsPlayer
                src={video.status === 'ready' ? getManifestUrl(id) : null}
                videoRef={videoRef}
                onPlay={onPlay}
                onPause={onPause}
                onSeeked={onSeeked}
                onTimeUpdate={onTimeUpdate}
              />
            </div>

            <h1 className={s.videoTitle}>{video.title}</h1>
            <div className={s.videoMeta}>
              {video.creator_name && (
                <span className={s.metaBadge}>👤 {video.creator_name}</span>
              )}
              {video.view_count != null && (
                <span className={s.metaBadge}>👁 {video.view_count.toLocaleString()} views</span>
              )}
              {video.status !== 'ready' && (
                <span className="alert alert-info" style={{ padding: '2px 10px', fontSize: 'var(--text-xs)' }}>
                  {video.status === 'processing' ? '⏳ Processing…' : '❌ Processing failed'}
                </span>
              )}
            </div>

            {/* Heatmap below player */}
            {video.status === 'ready' && (
              <div className={s.sidebarSection} style={{ marginTop: 'var(--space-5)' }}>
                <div className={s.sidebarTitle}>🔥 Viewer Heatmap</div>
                <div style={{ padding: 'var(--space-4)' }}>
                  <HeatmapChart videoId={id} onSeek={seekTo} />
                </div>
              </div>
            )}
          </div>

          {/* Sidebar — AI Summary */}
          <aside className={s.sidebar}>
            <div className={s.sidebarSection}>
              <div className={s.sidebarTitle}>🤖 AI Summary</div>
              <SummaryPanel videoId={id} onSeek={seekTo} />
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
