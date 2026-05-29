import client from './client'

export const uploadVideo   = (formData) =>
  client.post('/videos/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })

export const getVideo      = (id)       => client.get(`/videos/${id}`)
export const getVideoStatus = (id)      => client.get(`/videos/${id}/status`)
export const listVideos    = (params)   => client.get('/videos', { params })
export const updateVideo   = (id, data) => client.patch(`/videos/${id}`, data)
