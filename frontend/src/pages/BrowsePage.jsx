import { useState, useEffect, useCallback } from 'react'
import VideoGrid from '@/components/VideoGrid'
import { listVideos } from '@/api/videos'
import s from './BrowsePage.module.css'

const PER_PAGE = 12

export default function BrowsePage() {
  const [videos,   setVideos]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [search,   setSearch]   = useState('')
  const [query,    setQuery]    = useState('')   // committed search term
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)

  const totalPages = Math.ceil(total / PER_PAGE) || 1

  const fetchVideos = useCallback(() => {
    setLoading(true)
    setError('')
    listVideos({ page, q: query, limit: PER_PAGE })
      .then((res) => {
        // res may be an array or a paged object
        if (Array.isArray(res)) {
          setVideos(res); setTotal(res.length)
        } else {
          setVideos(res.items ?? res.data ?? []); setTotal(res.total ?? 0)
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, query])

  useEffect(() => { fetchVideos() }, [fetchVideos])

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    setQuery(search)
  }

  return (
    <div className={s.page}>
      <div className="container">
        <div className={s.header}>
          <h1 className={s.title}>Browse videos</h1>
          <form className={s.searchBar} onSubmit={handleSearch} role="search">
            <input
              className={s.searchInput}
              type="search"
              placeholder="Search videos…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search videos"
            />
            <button type="submit" className={s.searchBtn}>Search</button>
          </form>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: 'var(--space-6)' }}>{error}</div>
        )}

        <VideoGrid
          videos={videos}
          loading={loading}
          emptyTitle={query ? `No results for "${query}"` : 'No videos yet'}
          emptyText={query ? 'Try a different search term.' : 'Upload the first video!'}
        />

        {/* Pagination */}
        {!loading && total > PER_PAGE && (
          <div className={s.pagination}>
            <button
              className={s.pageBtn}
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Previous
            </button>
            <span className={s.pageInfo}>Page {page} of {totalPages}</span>
            <button
              className={s.pageBtn}
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
