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

/** Fetches all authorized pages for a collection endpoint using skip/limit pagination. */
export async function fetchAllPages(path, params = {}, pageSize = 100) {
  const all = []
  let skip = 0
  while (true) {
    const { data } = await api.get(path, { params: { ...params, skip, limit: pageSize } })
    const batch = Array.isArray(data) ? data : []
    all.push(...batch)
    if (batch.length < pageSize) break
    skip += pageSize
  }
  return all
}

/** Loads a complete authorized list on mount. Guarded against stale out-of-order responses. */
export function useList(path, onError, getParams = () => ({})) {
  const items = ref([])
  const loading = ref(false)
  let reqSeq = 0
  async function load() {
    const seq = ++reqSeq
    loading.value = true
    try {
      const data = await fetchAllPages(path, getParams())
      if (seq === reqSeq) items.value = data
    } catch (e) {
      if (seq === reqSeq) onError?.(e)
    } finally {
      if (seq === reqSeq) loading.value = false
    }
  }
  onMounted(load)
  return { items, loading, load }
}