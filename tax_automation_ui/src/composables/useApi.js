import { ref, onMounted } from 'vue'
import api from '../api'

/** Turns an axios / FastAPI error into one readable line. */
export function errMessage(e) {
  const d = e?.response?.data?.detail
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join('; ')
  if (typeof d === 'string') return d
  if (e?.message === 'Network Error') return 'Cannot reach the API. Is FastAPI running?'
  return e?.message || 'Something went wrong'
}

/** Page-level error text and a short-lived success toast. */
export function useNotify() {
  const error = ref('')
  const toast = ref('')
  let timer
  const flash = (msg) => {
    toast.value = msg
    clearTimeout(timer)
    timer = setTimeout(() => (toast.value = ''), 2500)
  }
  const fail = (e) => (error.value = errMessage(e))
  return { error, toast, flash, fail }
}

/** Loads a list on mount. getParams() is read on every load(), so filters stay current. */
export function useList(path, onError, getParams = () => ({})) {
  const items = ref([])
  const loading = ref(false)
  async function load() {
    loading.value = true
    try {
      items.value = (await api.get(path, { params: getParams() })).data
    } catch (e) {
      onError?.(e)
    } finally {
      loading.value = false
    }
  }
  onMounted(load)
  return { items, loading, load }
}