import client from './client'

export const postInteraction = (data) => client.post('/events/interaction', data)
