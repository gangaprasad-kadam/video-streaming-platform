import axios from 'axios'

const client = axios.create({
  withCredentials: true,   // sends session cookie on every request
  headers: { 'Content-Type': 'application/json' },
})

// Unwrap the SuccessResponse envelope: { success, data, message }
client.interceptors.response.use(
  (response) => response.data.data ?? response.data,
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
