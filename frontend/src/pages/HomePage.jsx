import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import VideoGrid from '@/components/VideoGrid'
import { getTrending, getRecommendations } from '@/api/trending'
import s from './HomePage.module.css'

export default function HomePage() {
  const { user } = useAuth()

  const [trending, setTrending]       = useState([])
  const [trendLoad, setTrendLoad]     = useState(true)
  const [trendErr,  setTrendErr]      = useState('')

  const [recs, setRecs]               = useState([])
  const [recsLoad, setRecsLoad]       = useState(false)
  const [recsErr,  setRecsErr]        = useState('')

  useEffect(() => {
    getTrending()
      .then(setTrending)
      .catch((e) => setTrendErr(e.message))
      .finally(() => setTrendLoad(false))
  }, [])

  useEffect(() => {
    if (!user?.id) return
    setRecsLoad(true)
    getRecommendations(user.id)
      .then(setRecs)
      .catch((e) => setRecsErr(e.message))
      .finally(() => setRecsLoad(false))
  }, [user])

  return (
    <div className={s.page}>
      {/* Hero */}
      <div className={s.hero}>
        <div className={s.heroInner}>
          <h1 className={s.heroTitle}>
            Watch what&apos;s<br />
            <span className={s.heroAccent}>trending now</span>
          </h1>
          <p className={s.heroSub}>
            Discover videos, follow creators, and dive into AI-powered highlights.
          </p>
        </div>
      </div>

      <div className="container">
        {/* Trending section */}
        <section className={s.section} aria-labelledby="trending-heading">
          <div className={s.sectionHeader}>
            <h2 className={s.sectionTitle} id="trending-heading">Trending</h2>
            <Link to="/browse" className={s.seeAll}>See all →</Link>
          </div>
          {trendErr && <div className={s.errorBox}>{trendErr}</div>}
          <VideoGrid
            videos={trending}
            loading={trendLoad}
            emptyTitle="No trending videos yet"
            emptyText="Be the first to upload something great."
          />
        </section>

        {/* Recommendations */}
        {user && (
          <section className={s.section} aria-labelledby="recs-heading">
            <div className={s.sectionHeader}>
              <h2 className={s.sectionTitle} id="recs-heading">Recommended for you</h2>
            </div>
            {recsErr && <div className={s.errorBox}>{recsErr}</div>}
            <VideoGrid
              videos={recs}
              loading={recsLoad}
              skeletonCount={4}
              emptyTitle="No recommendations yet"
              emptyText="Watch a few videos to get personalised suggestions."
            />
          </section>
        )}
      </div>
    </div>
  )
}
