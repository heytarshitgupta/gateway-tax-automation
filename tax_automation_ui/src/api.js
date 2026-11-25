import axios from 'axios'

const defaultHost = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : '127.0.0.1'
const defaultBaseURL = `http://${defaultHost}:8000/`

const configuredBaseURL = import.meta.env.VITE_API_BASE_URL
const baseURL = (configuredBaseURL || defaultBaseURL).replace(/\/?$/, '/')

const api = axios.create({
  baseURL,
  withCredentials: true,
})

// Collection endpoints requiring trailing slash to prevent FastAPI 307 redirects
const COLLECTION_ROUTES = new Set([
  '/clients',
  '/categories',
  '/tasks',
  '/groups',
  '/staff',
  '/messages',
  '/invoices',
  '/compliance-dates',
  '/matter-types',
])

api.interceptors.request.use((config) => {
  if (config.url && COLLECTION_ROUTES.has(config.url)) {
    config.url = config.url + '/'
  }
  return config
})

let isRedirectingToLogin = false

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        if (!isRedirectingToLogin) {
          isRedirectingToLogin = true
          localStorage.removeItem('active_staff_id')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
