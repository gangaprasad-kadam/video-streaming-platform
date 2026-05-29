import { useState, useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { getHistory } from '@/api/trending'
import VideoGrid from '@/components/VideoGrid'
import s from './HistoryPage.module.css'

export default function HistoryPage() {
  const { user, loading: authLoading } = useAuth()
  const [videos,  setVideos]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    if (!user?.id) return
    setLoading(true)
    getHistory(user.id, 40)
      .then(setVideos)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [user])

  if (authLoading) return null
  if (!user) return <Navigate to="/auth" replace />

  return (
    <div className={s.page}>
      <div className="container">
        <div className={s.header}>
          <h1 className={s.title}>Watch History</h1>
          {!loading && videos.length > 0 && (
            <span className={s.count}>{videos.length} video{videos.length !== 1 ? 's' : ''}</span>
          )}
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <VideoGrid
          videos={videos}
          loading={loading}
          emptyTitle="No watch history yet"
          emptyText="Videos you watch will appear here so you can easily come back to them."
        />
      </div>
    </div>
  )
}
