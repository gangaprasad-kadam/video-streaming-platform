import client from './client'

// Normalize backend VideoResponse → frontend VideoCard shape
const normVideo = (v) => ({
  ...v,
  id:            v.id,
  thumbnail_url: v.thumbnail_path ?? null,   // backend: thumbnail_path
  creator_id:    v.creator_id ?? null,        // keep for ownership checks
  creator_name:  v.creator_id ?? '',          // no name in response; show id as fallback
  view_count:    v.view_count ?? null,        // not in video-service response
  tags:          v.tags ?? [],
})

export const uploadVideo = (formData) =>
  client.post('/videos/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })

export const getVideo       = async (id)     => normVideo(await client.get(`/videos/${id}`))
export const getVideoStatus = (id)           => client.get(`/videos/${id}/status`)
export const updateVideo    = (id, data)     => client.patch(`/videos/${id}`, data)
export const deleteVideo    = (id)           => client.delete(`/videos/${id}`)

export const listVideos = async (params) => {
  // Returns PagedResponse: { data: [...VideoResponse], total, page, page_size }
  const res = await client.get('/videos', { params })
  if (Array.isArray(res)) return res.map(normVideo)
  return { ...res, data: (res.data ?? []).map(normVideo) }
}
