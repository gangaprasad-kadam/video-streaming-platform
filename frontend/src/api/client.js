import axios from 'axios'

const client = axios.create({
  withCredentials: true,   // sends session cookie on every request
  headers: { 'Content-Type': 'application/json' },
})

// Unwrap response envelopes:
//   SuccessResponse  { success, data, message }  → return data
//   PagedResponse    { data: [...], total, ... }  → return full object (preserves pagination)
client.interceptors.response.use(
  (response) => {
    const body = response.data
    // PagedResponse: has numeric `total` field (SuccessResponse never does)
    if (typeof body?.total === 'number') return body
    // SuccessResponse: unwrap .data
    return body?.data ?? body
  },
  (error) => {
    const message =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message ||
      'An unexpected error occurred'
    return Promise.reject(new Error(message))
  }
)

export default client
