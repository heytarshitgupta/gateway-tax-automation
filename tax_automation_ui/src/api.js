import axios from 'axios'

const hostname = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : '127.0.0.1'

const api = axios.create({
  baseURL: `http://${hostname}:8000/`,
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
