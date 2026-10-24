/**
 * api/client.ts
 * Axios instance configured for the backend API.
 * - Base URL points to the FastAPI backend at http://127.0.0.1:8000
 * - Request interceptor automatically attaches JWT from localStorage
 * - Response interceptor handles 401 (expired/missing token) by clearing
 *   localStorage and redirecting to /login
 */
import axios from 'axios'

const client = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Attach Authorization header from stored token on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401 Unauthorized: clear stored credentials and redirect to login
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
