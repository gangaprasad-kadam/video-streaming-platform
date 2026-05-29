import client from './client'

// Normalize TrendingVideoItem / RecommendationItem → VideoCard shape
const normItem = (v) => ({
  ...v,
  id:            v.video_id ?? v.id,
  thumbnail_url: v.thumbnail_path ?? null,
  creator_name:  v.creator_id ?? '',
  view_count:    null,
  status:        'ready',  // only ready videos appear in trending/recommendations
})

export const getTrending = async () => {
  // Backend: SuccessResponse[TrendingResponse] → { videos: [...], total }
  const res = await client.get('/trending')
  const items = res?.videos ?? (Array.isArray(res) ? res : [])
  return items.map(normItem)
}

export const getRecommendations = async (userId) => {
  // Backend: SuccessResponse[RecommendationsResponse] → { user_id, videos: [...], total }
  const res = await client.get(`/trending/recommendations/${userId}`)
  const items = res?.videos ?? (Array.isArray(res) ? res : [])
  return items.map(normItem)
}

export const getHistory = async (userId, limit = 20) => {
  // Backend: SuccessResponse[HistoryResponse] → { user_id, videos: [...], total }
  const res = await client.get(`/trending/history/${userId}`, { params: { limit } })
  const items = res?.videos ?? (Array.isArray(res) ? res : [])
  return items.map((v) => ({
    ...normItem(v),
    watched_at: v.watched_at,
  }))
}
