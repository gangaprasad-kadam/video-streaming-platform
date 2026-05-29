import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { getVideo, deleteVideo } from '@/api/videos'
import { getManifestUrl } from '@/api/stream'
import HlsPlayer from '@/components/HlsPlayer'
import SummaryPanel from '@/components/SummaryPanel'
import HeatmapChart from '@/components/HeatmapChart'
import useInteractionTracker from '@/hooks/useInteractionTracker'
import s from './PlayerPage.module.css'

export default function PlayerPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [video,   setVideo]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const videoRef = useRef(null)

  const { onPlay, onPause, onSeeked, onTimeUpdate: trackerTimeUpdate } = useInteractionTracker(id, user?.id, video?.creator_id ?? '')

  const RESUME_KEY = `vidstream:resume:${user?.id ?? 'anon'}:${id}`

  useEffect(() => {
    setLoading(true)
    getVideo(id)
      .then(setVideo)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  // Auto-seek to last saved position once video metadata is loaded
  useEffect(() => {
    if (!videoRef.current || !video) return
    const saved = parseFloat(localStorage.getItem(RESUME_KEY) || '0')
    if (saved > 5) {
      const handler = () => {
        videoRef.current.currentTime = saved
        videoRef.current.removeEventListener('loadedmetadata', handler)
      }
      videoRef.current.addEventListener('loadedmetadata', handler)
    }
  }, [video, RESUME_KEY])

  // Save playback position every 5 seconds
  const onTimeUpdate = (e) => {
    const t = e?.target?.currentTime ?? videoRef.current?.currentTime
    if (t > 5) localStorage.setItem(RESUME_KEY, String(Math.floor(t)))
    trackerTimeUpdate(e)
  }

  const seekTo = (time) => {
    if (videoRef.current) videoRef.current.currentTime = time
  }

  const handleDelete = async () => {
    if (!window.confirm('Delete this video? This cannot be undone.')) return
    try {
      await deleteVideo(id)
      localStorage.removeItem(RESUME_KEY)
      navigate('/', { replace: true })
    } catch (err) {
      alert('Failed to delete: ' + err.message)
    }
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
                <span className={s.metaBadge}>{video.creator_name}</span>
              )}
              {video.view_count != null && (
                <span className={s.metaBadge}>{video.view_count.toLocaleString()} views</span>
              )}
              {video.status !== 'ready' && (
                <span className="alert alert-info" style={{ padding: '2px 10px', fontSize: 'var(--text-xs)' }}>
                  {video.status === 'processing' ? 'Processing…' : 'Processing failed'}
                </span>
              )}
              {/* Delete button — creator only */}
              {user?.id === video.creator_id && (
                <button
                  onClick={handleDelete}
                  className={s.deleteBtn}
                  title="Delete video"
                  aria-label="Delete video"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                  Delete
                </button>
              )}
            </div>

            {/* Tags */}
            {video.tags?.length > 0 && (
              <div className={s.tagList}>
                {video.tags.map((tag) => (
                  <span key={tag} className={s.tag}>{tag}</span>
                ))}
              </div>
            )}

            {/* Heatmap — creator only */}
            {video.status === 'ready' && user?.id === video.creator_id && (
              <div className={s.sidebarSection} style={{ marginTop: 'var(--space-5)' }}>
                <div className={s.sidebarTitle}>Viewer Heatmap</div>
                <div style={{ padding: 'var(--space-4)' }}>
                  <HeatmapChart videoId={id} onSeek={seekTo} />
                </div>
              </div>
            )}
          </div>

          {/* Sidebar — AI Summary */}
          <aside className={s.sidebar}>
            <div className={s.sidebarSection}>
              <div className={s.sidebarTitle}>AI Summary</div>
              <SummaryPanel videoId={id} onSeek={seekTo} />
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
