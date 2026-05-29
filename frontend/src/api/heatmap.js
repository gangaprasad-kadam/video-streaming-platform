import client from './client'

// Normalize backend BucketItem { bucket, score, label }
//   → frontend shape  { segment_id, count, label }
const normBucket = (b) => ({ segment_id: b.bucket, count: b.score, label: b.label })

export const getHeatmap = async (videoId) => {
  const res = await client.get(`/heatmap/${videoId}`)
  return { ...res, segments: (res.buckets ?? []).map(normBucket) }
}

export const getLiveHeatmap = async (videoId) => {
  const res = await client.get(`/heatmap/${videoId}/live`)
  return { ...res, segments: (res.buckets ?? []).map(normBucket) }
}

export const getHighlights = async (videoId) => {
  const res = await client.get(`/heatmap/${videoId}/highlights`)
  return { ...res, highlights: (res.highlights ?? []).map(normBucket) }
}

// SSE stream URL — used directly with EventSource, not axios
// Backend pushes: { segments: [{ segment_id, count, label }] }
export const getHeatmapStreamUrl = (videoId) => `/heatmap/${videoId}/stream`
