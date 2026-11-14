import axios from 'axios'

const defaultHost = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : '127.0.0.1'
const defaultBaseURL = `http://${defaultHost}:8000/`

const configuredBaseURL = import.meta.env.VITE_API_BASE_URL
const baseURL = (configuredBaseURL || defaultBaseURL).replace(/\/?$/, '/')

const api = axios.create({
  baseURL,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        localStorage.removeItem('active_staff_id')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
