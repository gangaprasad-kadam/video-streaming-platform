import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { listVideos } from '@/api/videos'
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
                    : '🎬'
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
              </Link>
            ))}
          </div>
        )}

        {/* Live Heatmap panel */}
        {selected && (
          <div className={s.heatPanel}>
            <div className={s.heatHeader}>
              🔥 Live Heatmap
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
