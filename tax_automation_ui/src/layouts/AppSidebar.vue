<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import api from '../api'
import { useTheme } from '../composables/useTheme'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const router = useRouter()
const { dark, init, toggle } = useTheme()
const {
  isHigh,
  isAuthenticatedHigh,
  selectedStaffId,
  staffList,
  switchStaffContext,
  logout,
  loadStaff,
} = useCurrentStaff()

const online = ref(null) // null = checking

const menu = computed(() => {
  const items = [
    { to: '/dashboard', label: 'Dashboard', icon: '📊' },
    { to: '/clients', label: 'Clients', icon: '👥' },
  ]
  // Staff Management is shown ONLY when effective permissions are HIGH
  if (isHigh.value) {
    items.push({ to: '/staff', label: 'Staff', icon: '🧑‍💼' })
  }
  items.push({ to: '/profile', label: 'My Profile', icon: '👤' })
  items.push(
    { to: '/tasks', label: 'Matters & Tasks', icon: '📋' },
    { to: '/messages', label: 'Communication Log', icon: '💬' },
  )
  return items
})

async function handleSwitchStaff(staffId) {
  try {
    await switchStaffContext(staffId)
    // If effective permissions are no longer HIGH and user is currently on /staff, navigate to /dashboard
    if (!isHigh.value && router.currentRoute.value.path === '/staff') {
      router.push('/dashboard')
    }
  } catch (err) {
    console.error('Failed to switch staff context:', err)
  }
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

onMounted(async () => {
  init()
  loadStaff()
  online.value = await api.get('/categories').then(() => true, () => false)
})
</script>

<template>
  <aside class="side">
    <div class="brand">
      <div class="logo">GS</div>
      <div>
        <div class="brand-name">Gateway Solutions</div>
        <div class="brand-tag">Tax Office Automation</div>
      </div>
    </div>

    <nav aria-label="Main">
      <RouterLink v-for="m in menu" :key="m.to" :to="m.to" class="side-item">
        <span class="side-ico" aria-hidden="true">{{ m.icon }}</span>{{ m.label }}
      </RouterLink>
    </nav>

    <div class="side-foot">
      <!-- Active staff dropdown: available and visible ONLY to authenticated HIGH users -->
      <div v-if="isAuthenticatedHigh" class="side-staff-box">
        <label for="active-staff-select" class="side-staff-label">Active Staff</label>
        <select
          id="active-staff-select"
          class="side-staff-select"
          :value="selectedStaffId"
          @change="handleSwitchStaff($event.target.value)"
        >
          <option
            v-for="s in staffList"
            :key="s.id"
            :value="s.id"
            :disabled="!s.is_active"
          >
            {{ s.name }} ({{ s.access_level }})
          </option>
        </select>
      </div>

      <button class="side-btn" @click="toggle">
        <span aria-hidden="true">{{ dark ? '☀️' : '🌙' }}</span>{{ dark ? 'Light mode' : 'Dark mode' }}
      </button>

      <button class="side-btn logout-btn" @click="handleLogout" title="Sign out of your account">
        <span aria-hidden="true">🚪</span>Sign out
      </button>

      <div class="side-status">
        <span class="led" :class="{ on: online === true, off: online === false }"></span>
        {{ online === null ? 'Checking API…' : online ? 'API connected' : 'API offline' }}
      </div>
    </div>
  </aside>
</template>

<style scoped>
.side-staff-box {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.side-staff-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #bfe0d6;
  font-weight: 600;
}
.side-staff-select {
  font: inherit;
  font-size: 0.85rem;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--side-line);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  cursor: pointer;
  width: 100%;
  outline: none;
}
.side-staff-select option {
  background: var(--side);
  color: #fff;
}
.logout-btn {
  color: #ffcccc;
}
.logout-btn:hover {
  background: rgba(255, 80, 80, 0.2);
}
</style>
