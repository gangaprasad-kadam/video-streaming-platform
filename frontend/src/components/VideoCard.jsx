import { Link } from 'react-router-dom'
import s from './VideoCard.module.css'

function formatDuration(seconds) {
  if (!seconds) return null
  const m = Math.floor(seconds / 60)
  const ss = String(seconds % 60).padStart(2, '0')
  return `${m}:${ss}`
}

function formatViews(n) {
  if (!n) return null
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K views`
  return `${n} views`
}

export function VideoCardSkeleton() {
  return (
    <div className={s.cardSkeleton}>
      <div className={s.skeletonThumb} />
      <div className={s.skeletonInfo}>
        <div className={s.skeletonLine} />
        <div className={`${s.skeletonLine} ${s.skeletonShort}`} />
      </div>
    </div>
  )
}

export default function VideoCard({ video }) {
  const { id, title, thumbnail_url, creator_name, duration, view_count, status } = video

  return (
    <Link to={`/videos/${id}`} className={s.card} data-testid="video-card">
      <div className={s.thumb}>
        {thumbnail_url ? (
          <img className={s.thumbImg} src={thumbnail_url} alt={title} loading="lazy" />
        ) : (
          <div className={s.thumbPlaceholder} aria-hidden>🎬</div>
        )}
        {duration && <span className={s.duration}>{formatDuration(duration)}</span>}
        {status === 'processing' && (
          <span className={`${s.statusBadge} ${s.statusProcessing}`}>Processing</span>
        )}
        {status === 'failed' && (
          <span className={`${s.statusBadge} ${s.statusFailed}`}>Failed</span>
        )}
      </div>

      <div className={s.info}>
        <h3 className={s.title}>{title}</h3>
        <div className={s.meta}>
          {creator_name && <span className={s.creator}>{creator_name}</span>}
          {view_count != null && <span className={s.views}>{formatViews(view_count)}</span>}
        </div>
      </div>
    </Link>
  )
}
