<script setup>
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const { authenticatedUser, selectedStaff, isAuthenticatedHigh } = useCurrentStaff()

const isPreviewing = computed(() => {
  return (
    isAuthenticatedHigh.value &&
    selectedStaff.value &&
    authenticatedUser.value &&
    selectedStaff.value.id !== authenticatedUser.value.id
  )
})

const authorityClass = computed(() => {
  const level = authenticatedUser.value?.access_level?.toLowerCase()
  if (level === 'high') return 'authority-high'
  if (level === 'medium') return 'authority-medium'
  return 'authority-low'
})
</script>

<template>
  <div class="shell">
    <AppSidebar />
    <div class="main-wrapper">
      <header class="app-header">
        <div class="identity-block">
          <span class="staff-name">{{ authenticatedUser?.name || 'Staff' }}</span>
          <span class="sep" aria-hidden="true">•</span>
          <span class="staff-role">{{ authenticatedUser?.role || 'Staff' }}</span>
          <span class="chip authority-chip" :class="authorityClass">
            {{ authenticatedUser?.access_level || 'LOW' }}
          </span>
          <span v-if="isPreviewing" class="preview-chip" title="Active staff preview context">
            Viewing: {{ selectedStaff?.name }}
          </span>
        </div>
      </header>
      <main class="page"><RouterView /></main>
    </div>
  </div>
</template>

<style scoped>
.main-wrapper {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0.65rem 2.25rem;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  font-size: 0.85rem;
  min-height: 44px;
}

.identity-block {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  color: var(--ink);
}

.staff-name {
  font-weight: 600;
  color: var(--ink);
}

.staff-role {
  color: var(--muted);
}

.sep {
  color: var(--line);
  user-select: none;
}

.authority-chip {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0;
}

.authority-high {
  background: var(--ok-soft);
  color: var(--ok);
  border: 1px solid var(--ok);
}

.authority-medium {
  background: var(--warn-soft);
  color: var(--warn);
  border: 1px solid var(--warn);
}

.authority-low {
  background: var(--sunken);
  color: var(--muted);
  border: 1px solid var(--line);
}

.preview-chip {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px dashed var(--accent);
}
</style>
