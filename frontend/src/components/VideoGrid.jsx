import VideoCard, { VideoCardSkeleton } from './VideoCard'
import s from './VideoGrid.module.css'

export default function VideoGrid({ videos, loading, skeletonCount = 8, emptyTitle = 'No videos found', emptyText = '' }) {
  if (loading) {
    return (
      <div className={s.grid}>
        {Array.from({ length: skeletonCount }, (_, i) => (
          <VideoCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (!videos?.length) {
    return (
      <div className={s.grid}>
        <div className={s.empty}>
          <div className={s.emptyIcon} aria-hidden>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m10 9 5 3-5 3V9z"/></svg>
          </div>
          <div className={s.emptyTitle}>{emptyTitle}</div>
          {emptyText && <div className={s.emptyText}>{emptyText}</div>}
        </div>
      </div>
    )
  }

  return (
    <div className={s.grid}>
      {videos.map((v) => <VideoCard key={v.id} video={v} />)}
    </div>
  )
}
