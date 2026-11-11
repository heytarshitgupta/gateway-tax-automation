import { ref, computed } from 'vue'
import api from '../api'

const authenticatedUser = ref(null)
const selectedStaff = ref(null)
const authChecked = ref(false)
const staffList = ref([])
const loading = ref(false)

// Authenticated user status (used exclusively for HIGH context switching feature)
const isAuthenticatedHigh = computed(() => authenticatedUser.value?.access_level === 'HIGH')

// Effective working staff identity
const effectiveStaff = computed(() => {
  if (isAuthenticatedHigh.value && selectedStaff.value) {
    return selectedStaff.value
  }
  return authenticatedUser.value
})

const effectiveAccessLevel = computed(() => effectiveStaff.value?.access_level || null)

// Effective permissions (drive all UI controls, page access, actions)
const isHigh = computed(() => effectiveAccessLevel.value === 'HIGH')
const isMedium = computed(() => effectiveAccessLevel.value === 'MEDIUM')
const isLow = computed(() => effectiveAccessLevel.value === 'LOW')

// Working staff ID (for task assignment, ownership checks, filters)
const activeStaffId = computed(() => effectiveStaff.value?.id || null)

// Selected working context ID (for dropdown)
const selectedStaffId = computed(() => selectedStaff.value?.id || authenticatedUser.value?.id || null)

const currentUser = computed(() => effectiveStaff.value)
const currentStaff = computed(() => effectiveStaff.value)
const accessLevel = computed(() => effectiveAccessLevel.value)

async function checkAuth() {
  try {
    const res = await api.get('/auth/me')
    authenticatedUser.value = res.data
    selectedStaff.value = res.data.selected_staff || res.data
    authChecked.value = true
    return res.data
  } catch (err) {
    authenticatedUser.value = null
    selectedStaff.value = null
    authChecked.value = true
    return null
  }
}

async function login(email, password) {
  const res = await api.post('/auth/login', { email, password })
  authenticatedUser.value = res.data
  selectedStaff.value = res.data.selected_staff || res.data
  authChecked.value = true
  return res.data
}

async function logout() {
  try {
    await api.post('/auth/logout')
  } catch (err) {
    // proceed with client cleanup even if network fails
  } finally {
    authenticatedUser.value = null
    selectedStaff.value = null
    authChecked.value = true
    localStorage.removeItem('active_staff_id')
  }
}

async function switchStaffContext(staffId) {
  if (!isAuthenticatedHigh.value) return
  const numId = Number(staffId)
  const res = await api.post('/auth/select-context', { staff_id: numId })
  authenticatedUser.value = res.data
  selectedStaff.value = res.data.selected_staff || res.data
  return res.data
}

async function updateProfile(payload) {
  const res = await api.patch('/auth/profile', payload)
  authenticatedUser.value = res.data
  selectedStaff.value = res.data.selected_staff || res.data
  // Update local staffList if present so dropdown and tables reflect any name change
  const updatedId = res.data.id
  const idx = staffList.value.findIndex((s) => s.id === updatedId)
  if (idx !== -1) {
    staffList.value[idx] = { ...staffList.value[idx], name: res.data.name, mobile_number: res.data.mobile_number }
  }
  return res.data
}

async function loadStaff() {
  if (!authenticatedUser.value) return
  loading.value = true
  try {
    const res = await api.get('/staff/')
    staffList.value = res.data || []
  } catch (err) {
    if (err?.response?.status !== 401 && err?.response?.status !== 403) {
      console.error('Failed to load staff list:', err)
    }
  } finally {
    loading.value = false
  }
}

export function useCurrentStaff() {
  return {
    authenticatedUser,
    selectedStaff,
    effectiveStaff,
    isAuthenticatedHigh,
    selectedStaffId,
    currentUser,
    currentStaff,
    activeStaffId,
    accessLevel,
    effectiveAccessLevel,
    isHigh,
    isMedium,
    isLow,
    authChecked,
    staffList,
    loading,
    checkAuth,
    login,
    logout,
    switchStaffContext,
    updateProfile,
    loadStaff,
  }
}
