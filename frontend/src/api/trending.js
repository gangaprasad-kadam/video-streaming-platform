import client from './client'

export const getTrending        = ()       => client.get('/trending')
export const getRecommendations = (userId) => client.get(`/recommendations/${userId}`)
