import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { listVideos, deleteVideo } from '@/api/videos'
import HeatmapChart from '@/components/HeatmapChart'
import s from './DashboardPage.module.css'

export default function DashboardPage() {
  const { user } = useAuth()
  const [videos,  setVideos]  = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    listVideos({ creator_id: user?.id, limit: 50 })
      .then((res) => {
        const list = Array.isArray(res) ? res : res.items ?? res.data ?? []
        setVideos(list)
        if (list.length) setSelected(list[0].id)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  const handleDelete = async (e, videoId) => {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm('Delete this video? This cannot be undone.')) return
    try {
      await deleteVideo(videoId)
      setVideos((prev) => prev.filter((v) => v.id !== videoId))
      if (selected === videoId) setSelected(null)
    } catch (err) {
      alert('Failed to delete: ' + err.message)
    }
  }

  const ready  = videos.filter((v) => v.status === 'ready').length
  const totalViews = videos.reduce((acc, v) => acc + (v.view_count || 0), 0)

  return (
    <div className={s.page}>
      <div className="container">
        <div className={s.header}>
          <h1 className={s.title}>Creator Dashboard</h1>
          <Link to="/upload" style={{ color: 'var(--color-accent-text)', fontSize: 'var(--text-sm)', fontWeight: 'var(--fw-medium)' }}>
            ＋ Upload new video
          </Link>
        </div>

        {/* Stats */}
        <div className={s.stats}>
          <div className={s.stat}>
            <div className={s.statLabel}>Total videos</div>
            <div className={s.statValue}>{loading ? '…' : videos.length}</div>
          </div>
          <div className={s.stat}>
            <div className={s.statLabel}>Ready</div>
            <div className={s.statValue}>{loading ? '…' : ready}</div>
          </div>
          <div className={s.stat}>
            <div className={s.statLabel}>Total views</div>
            <div className={s.statValue}>{loading ? '…' : totalViews.toLocaleString()}</div>
          </div>
        </div>

        {/* Video list */}
        {!loading && videos.length === 0 ? (
          <div className={s.empty}>No videos yet — <Link to="/upload">upload your first one</Link></div>
        ) : (
          <div className={s.videoList}>
            {videos.map((v) => (
              <Link
                key={v.id}
                to={`/videos/${v.id}`}
                className={s.videoRow}
                onClick={(e) => { e.preventDefault(); setSelected(v.id) }}
              >
                <div className={s.rowThumb}>
                  {v.thumbnail_url
                    ? <img className={s.rowThumbImg} src={v.thumbnail_url} alt={v.title} />
                    : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m10 9 5 3-5 3V9z"/></svg>
                  }
                </div>
                <div className={s.rowInfo}>
                  <div className={s.rowTitle}>{v.title}</div>
                  <div className={s.rowMeta}>{(v.view_count || 0).toLocaleString()} views</div>
                </div>
                <span className={`${s.rowStatus} ${
                  v.status === 'ready'      ? s.statusReady :
                  v.status === 'processing' ? s.statusProcessing :
                  v.status === 'failed'     ? s.statusFailed : ''
                }`}>
                  {v.status}
                </span>
                <button
                  className={s.deleteBtn}
                  onClick={(e) => handleDelete(e, v.id)}
                  title="Delete video"
                  aria-label={`Delete ${v.title}`}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                </button>
              </Link>
            ))}
          </div>
        )}

        {/* Live Heatmap panel */}
        {selected && (
          <div className={s.heatPanel}>
            <div className={s.heatHeader}>
              <span style={{display:'flex',alignItems:'center',gap:'6px'}}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7" strokeDasharray="2 3"/></svg>
                Live Heatmap
              </span>
              <select
                className={s.heatSelect}
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                aria-label="Select video for heatmap"
              >
                {videos.filter((v) => v.status === 'ready').map((v) => (
                  <option key={v.id} value={v.id}>{v.title}</option>
                ))}
              </select>
            </div>
            <div className={s.heatBody}>
              <HeatmapChart videoId={selected} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
