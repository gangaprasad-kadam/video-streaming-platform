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
          <div className={s.emptyIcon} aria-hidden>🎬</div>
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
