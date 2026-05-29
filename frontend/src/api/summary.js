import client from './client'

export const getSummary = (videoId) => client.get(`/summary/${videoId}`)
