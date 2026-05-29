import client from './client'

export const getHeatmap      = (videoId) => client.get(`/heatmap/${videoId}`)
export const getLiveHeatmap  = (videoId) => client.get(`/heatmap/${videoId}/live`)
export const getHighlights   = (videoId) => client.get(`/heatmap/${videoId}/highlights`)
// SSE stream URL — used directly with EventSource, not axios
export const getHeatmapStreamUrl = (videoId) => `/heatmap/${videoId}/stream`
