<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useList } from '../composables/useApi'
import { formatIstTimestamp } from '../utils/dates'
import PageHeader from '../layouts/PageHeader.vue'

const route = useRoute()
const router = useRouter()

const messages = ref([])
const loading = ref(false)
const error = ref('')

// Load clients to resolve client names
const { items: clients } = useList('/clients/')
const clientName = (id) => {
  const c = clients.value.find((cl) => cl.id === id)
  return c ? c.business_name : `Client #${id}`
}

// Filter & server-side pagination state
const filterDate = ref(route.query.date || '')
const filterStatusGroup = ref(route.query.status_group || '')
const currentPage = ref(1)
const pageSize = 20
const hasNextPage = ref(false)
let fetchSeq = 0

const STATUS_GROUPS = [
  { value: '', label: 'All Statuses' },
  { value: 'sent', label: 'Sent (Sent, Delivered, Read)' },
  { value: 'failed', label: 'Failed' },
]

async function fetchMessages() {
  const seq = ++fetchSeq
  loading.value = true
  error.value = ''
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize,
      limit: pageSize + 1,
    }
    if (filterDate.value) {
      params.date = filterDate.value
    }
    if (filterStatusGroup.value) {
      params.status_group = filterStatusGroup.value
    }
    const { data } = await api.get('/messages/', { params })
    if (seq !== fetchSeq) return
    const rows = Array.isArray(data) ? data : []
    hasNextPage.value = rows.length > pageSize
    messages.value = hasNextPage.value ? rows.slice(0, pageSize) : rows
  } catch (err) {
    if (seq !== fetchSeq) return
    error.value = err.response?.data?.detail || err.message || 'Failed to load messages.'
  } finally {
    if (seq === fetchSeq) {
      loading.value = false
    }
  }
}

function updateQuery() {
  currentPage.value = 1
  const query = {}
  if (filterDate.value) query.date = filterDate.value
  if (filterStatusGroup.value) query.status_group = filterStatusGroup.value

  router.replace({ query }).catch(() => {})
  fetchMessages()
}

function goToPage(nextPage) {
  if (nextPage < 1) return
  if (nextPage > currentPage.value && !hasNextPage.value) return
  currentPage.value = nextPage
  fetchMessages()
}

function clearFilters() {
  filterDate.value = ''
  filterStatusGroup.value = ''
  currentPage.value = 1
  updateQuery()
}

function formatDate(ts) {
  return formatIstTimestamp(ts)
}

function statusBadgeClass(status) {
  if (['SENT', 'DELIVERED', 'READ'].includes(status)) return 'badge-sent'
  if (status === 'FAILED') return 'badge-failed'
  return 'badge-other'
}

watch(
  () => route.query,
  (newQuery) => {
    const dateVal = newQuery.date || ''
    const sgVal = newQuery.status_group || ''
    if (dateVal !== filterDate.value || sgVal !== filterStatusGroup.value) {
      filterDate.value = dateVal
      filterStatusGroup.value = sgVal
      currentPage.value = 1
      fetchMessages()
    }
  }
)

onMounted(() => {
  fetchMessages()
})
</script>

<template>
  <section class="messages-view">
    <PageHeader
      title="Communication Log"
      subtitle="Audit trail of automated notifications and WhatsApp messages sent to clients."
    />

    <p v-if="error" class="banner error" role="alert">{{ error }}</p>

    <!-- Filters Bar -->
    <div class="filters">
      <div class="filter-item">
        <label for="msg-date-filter" class="inline">Date:
          <input
            id="msg-date-filter"
            v-model="filterDate"
            type="date"
            aria-label="Filter messages by date"
            @change="updateQuery"
          />
        </label>
      </div>

      <div class="filter-item">
        <label for="msg-status-filter" class="inline">Status:
          <select
            id="msg-status-filter"
            v-model="filterStatusGroup"
            aria-label="Filter messages by status group"
            @change="updateQuery"
          >
            <option v-for="g in STATUS_GROUPS" :key="g.value" :value="g.value">
              {{ g.label }}
            </option>
          </select>
        </label>
      </div>

      <button
        v-if="filterDate || filterStatusGroup"
        type="button"
        class="btn mini"
        @click="clearFilters"
      >
        Clear filters
      </button>

      <span class="count-indicator">
        Showing <strong>{{ messages.length }}</strong> message{{ messages.length === 1 ? '' : 's' }}
      </span>
    </div>

    <!-- Messages Table -->
    <div class="table-wrap" :aria-busy="loading">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Client</th>
            <th>Type</th>
            <th>Content</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="empty">Loading communication history…</td>
          </tr>
          <tr v-else-if="messages.length === 0">
            <td colspan="5" class="empty">
              No communication records found matching current criteria.
            </td>
          </tr>
          <tr v-for="msg in messages" :key="msg.id">
            <td class="small">{{ formatDate(msg.sent_timestamp) }}</td>
            <td>
              <strong>{{ clientName(msg.client_id) }}</strong>
            </td>
            <td>
              <span class="chip">{{ msg.message_type }}</span>
            </td>
            <td class="msg-content">{{ msg.message_content }}</td>
            <td>
              <span class="status-badge" :class="statusBadgeClass(msg.status)">
                {{ msg.status }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Server-Side Pagination -->
    <div v-if="currentPage > 1 || hasNextPage || messages.length > 0" class="pagination">
      <button
        type="button"
        class="btn mini"
        :disabled="loading || currentPage <= 1"
        @click="goToPage(currentPage - 1)"
      >
        Previous
      </button>
      <span class="page-indicator">Page {{ currentPage }}</span>
      <button
        type="button"
        class="btn mini"
        :disabled="loading || !hasNextPage"
        @click="goToPage(currentPage + 1)"
      >
        Next
      </button>
    </div>
  </section>
</template>

<style scoped>
.messages-view {
  display: flex;
  flex-direction: column;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1rem;
}

.page-indicator {
  font-size: 0.85rem;
  color: var(--muted);
}

.filters {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}

.filter-item input,
.filter-item select {
  width: auto;
}

.count-indicator {
  margin-left: auto;
  font-size: 0.88rem;
  color: var(--muted);
}

.msg-content {
  max-width: 400px;
  word-break: break-word;
}

.status-badge {
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-sent {
  background: var(--ok-soft);
  color: var(--ok);
}

.badge-failed {
  background: var(--danger-soft);
  color: var(--danger);
}

.badge-other {
  background: var(--sunken);
  color: var(--muted);
}
</style>
