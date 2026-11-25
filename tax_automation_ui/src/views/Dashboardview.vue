<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { todayStr, day, daysFromToday, fmtDate } from '../utils/dates'
import PageHeader from '../layouts/PageHeader.vue'
import MattersDrawer from '../components/MattersDrawer.vue'
import { errMessage, useList } from '../composables/useApi'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const router = useRouter()
const { isHigh, activeStaffId } = useCurrentStaff()

// Reminder job path
const RUN_JOB_PATH = '/automation/run-reminders'

const summary = ref({
  total_clients: 0,
  active_clients: 0,
  inactive_clients: 0,
  messages_sent_today: 0,
  messages_failed_today: 0,
  due_within_7_days: 0,
  assigned_tasks: 0,
  total_matters: 0,
  total_tasks: null,
})
const loadingSummary = ref(false)
const summaryError = ref('')

// Compliance dates for upcoming detail panel
const problems = ref([])
const miss = (name) => (e) => problems.value.push(`Could not load ${name}: ${errMessage(e)}`)
const { items: dates, loading: loadingDates, load: loadDates } = useList('/compliance-dates/', miss('compliance dates'))
const { items: categories } = useList('/categories/', miss('categories'))

const catName = (id) => categories.value.find((c) => c.id === id)?.name || ''
const upcoming = computed(() =>
  dates.value
    .filter((d) => d.due_date && daysFromToday(d.due_date) >= 0 && daysFromToday(d.due_date) <= 7)
    .sort((a, b) => day(a.due_date).localeCompare(day(b.due_date)))
)
const dueText = (d) => ['Today', 'Tomorrow'][daysFromToday(d)] ?? `In ${daysFromToday(d)} days`

// Matter catalogue drawer state
const showMattersDrawer = ref(false)
const mattersAddMode = ref(false)
let summaryRequestSeq = 0

async function loadDashboardSummary() {
  const seq = ++summaryRequestSeq
  loadingSummary.value = true
  summaryError.value = ''
  if (!isHigh.value) {
    summary.value.total_tasks = null
  }
  try {
    const today = todayStr()
    const { data } = await api.get('/dashboard/summary', { params: { date: today } })
    if (seq !== summaryRequestSeq) return
    summary.value = {
      total_clients: data.total_clients ?? 0,
      active_clients: data.active_clients ?? 0,
      inactive_clients: data.inactive_clients ?? 0,
      messages_sent_today: data.messages_sent_today ?? 0,
      messages_failed_today: data.messages_failed_today ?? 0,
      due_within_7_days: data.due_within_7_days ?? 0,
      assigned_tasks: data.assigned_tasks ?? 0,
      total_matters: data.total_matters ?? 0,
      total_tasks: isHigh.value ? (data.total_tasks ?? null) : null,
    }
  } catch (err) {
    if (seq !== summaryRequestSeq) return
    summaryError.value = err.response?.data?.detail || err.message || 'Could not load dashboard statistics.'
  } finally {
    if (seq === summaryRequestSeq) {
      loadingSummary.value = false
    }
  }
}

// Navigation helpers for cards
function navigateToClients(filter = 'all') {
  if (filter === 'active') {
    router.push('/clients?filter=active')
  } else if (filter === 'inactive') {
    router.push('/clients?filter=inactive')
  } else {
    router.push('/clients')
  }
}

function navigateToMessages(statusGroup) {
  const today = todayStr()
  router.push(`/messages?date=${today}&status_group=${statusGroup}`)
}

function scrollToCompliance() {
  const el = document.getElementById('compliance-panel')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function navigateToAssignedTasks() {
  if (activeStaffId.value) {
    router.push(`/tasks?staff_id=${activeStaffId.value}`)
  } else {
    router.push('/tasks')
  }
}

function navigateToAllTasks() {
  router.push('/tasks')
}

function navigateToCreateTask() {
  router.push('/tasks?action=create')
}

function openMatterCatalogue(addMode = false) {
  mattersAddMode.value = addMode
  showMattersDrawer.value = true
}

// Reminder job
const running = ref(false)
const jobResult = ref('')
const jobError = ref('')

async function runJob() {
  running.value = true
  jobResult.value = jobError.value = ''
  problems.value = []
  try {
    const { data } = await api.post(RUN_JOB_PATH)
    jobResult.value = typeof data === 'string' ? data : data?.message || 'Reminder job finished.'
    loadDashboardSummary()
    loadDates()
  } catch (e) {
    const s = e?.response?.status
    jobError.value = [404, 405].includes(s)
      ? `The API has no ${RUN_JOB_PATH} endpoint (HTTP ${s}).`
      : e?.response?.data?.detail || e.message || 'The reminder job failed.'
  } finally {
    running.value = false
  }
}

// Watch profile context changes
watch([activeStaffId, isHigh], () => {
  loadDashboardSummary()
  loadDates()
})

onMounted(() => {
  loadDashboardSummary()
})
</script>

<template>
  <section class="dashboard-page">
    <PageHeader title="Dashboard" subtitle="Overview of client engagement and WhatsApp automation performance." />

    <p v-if="summaryError" class="banner error" role="alert">{{ summaryError }}</p>
    <p v-for="p in problems" :key="p" class="banner error" role="alert">{{ p }}</p>

    <!-- Exactly Eight Statistic Cards -->
    <div class="cards" :aria-busy="loadingSummary">
      <!-- 1. Total clients -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="View all clients"
        @click="navigateToClients('all')"
        @keydown.enter="navigateToClients('all')"
      >
        <span class="badge blue" aria-hidden="true">👥</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.total_clients }}</div>
          <div class="lbl">Total clients</div>
        </div>
      </div>

      <!-- 2. Active clients -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="View active clients"
        @click="navigateToClients('active')"
        @keydown.enter="navigateToClients('active')"
      >
        <span class="badge green" aria-hidden="true">✅</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.active_clients }}</div>
          <div class="lbl">Active clients</div>
        </div>
      </div>

      <!-- 3. Inactive clients -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="View inactive clients"
        @click="navigateToClients('inactive')"
        @keydown.enter="navigateToClients('inactive')"
      >
        <span class="badge grey" aria-hidden="true">⏸️</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.inactive_clients }}</div>
          <div class="lbl">Inactive clients</div>
        </div>
      </div>

      <!-- 4. Messages sent today -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="View messages sent today"
        @click="navigateToMessages('sent')"
        @keydown.enter="navigateToMessages('sent')"
      >
        <span class="badge mint" aria-hidden="true">💬</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.messages_sent_today }}</div>
          <div class="lbl">Messages sent today</div>
        </div>
      </div>

      <!-- 5. Failed today -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="View failed messages today"
        @click="navigateToMessages('failed')"
        @keydown.enter="navigateToMessages('failed')"
      >
        <span class="badge red" aria-hidden="true">⚠️</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.messages_failed_today }}</div>
          <div class="lbl">Failed today</div>
        </div>
      </div>

      <!-- 6. Due within 7 days -->
      <div
        class="stat interactive-card"
        tabindex="0"
        role="button"
        aria-label="Scroll to upcoming compliance dates"
        @click="scrollToCompliance"
        @keydown.enter="scrollToCompliance"
      >
        <span class="badge amber" aria-hidden="true">🗓️</span>
        <div>
          <div class="num">{{ loadingSummary ? '…' : summary.due_within_7_days }}</div>
          <div class="lbl">Due within 7 days</div>
        </div>
      </div>

      <!-- 7. Assigned tasks Card -->
      <div
        class="stat interactive-card assigned-tasks-card"
        tabindex="0"
        role="button"
        aria-label="View assigned tasks"
        @click="navigateToAssignedTasks"
        @keydown.enter="navigateToAssignedTasks"
      >
        <span class="badge blue" aria-hidden="true">📋</span>
        <div class="card-content-wrap">
          <div class="num">{{ loadingSummary ? '…' : summary.assigned_tasks }}</div>
          <div class="lbl">Assigned tasks</div>
          <div
            v-if="isHigh && summary.total_tasks !== null"
            class="total-tasks-subtext metric-subtext"
            tabindex="0"
            role="button"
            title="View all organization tasks"
            aria-label="View all organization tasks"
            @click.stop="navigateToAllTasks"
            @keydown.enter.stop="navigateToAllTasks"
          >
            Total tasks: <strong>{{ summary.total_tasks }}</strong>
          </div>
          <button
            v-if="isHigh"
            type="button"
            class="card-action-btn create-task-btn"
            title="Create new task"
            aria-label="Create new task"
            @click.stop="navigateToCreateTask"
          >
            + Create Task
          </button>
        </div>
      </div>

      <!-- 8. Total matters Card -->
      <div
        class="stat interactive-card total-matters-card"
        tabindex="0"
        role="button"
        aria-label="View matter catalogue"
        @click="openMatterCatalogue(false)"
        @keydown.enter="openMatterCatalogue(false)"
      >
        <span class="badge mint" aria-hidden="true">📑</span>
        <div class="card-content-wrap">
          <div class="num">{{ loadingSummary ? '…' : summary.total_matters }}</div>
          <div class="lbl">Total matters</div>
          <button
            v-if="isHigh"
            type="button"
            class="card-action-btn"
            title="Add matter directly"
            aria-label="Add matter directly"
            @click.stop="openMatterCatalogue(true)"
          >
            + Add Matter
          </button>
        </div>
      </div>
    </div>

    <!-- Automation Engine Panel -->
    <div class="panel engine">
      <div>
        <h2>Automation engine</h2>
        <p>
          The scheduler runs automatically every day at 09:00 to send GST/TDS reminders for compliance
          dates due in 7, 3, and 1 day(s). You can also trigger it manually here for testing or demos.
        </p>
      </div>
      <button class="run" :disabled="running" @click="runJob">
        {{ running ? 'Running…' : 'Run reminder job now' }}
      </button>
    </div>
    <p v-if="jobResult" class="banner ok" role="status" style="margin-top: 1rem">{{ jobResult }}</p>
    <p v-if="jobError" class="banner error" role="alert" style="margin-top: 1rem">{{ jobError }}</p>

    <!-- Compliance Dates Panel -->
    <div id="compliance-panel" class="panel">
      <h2>Compliance dates in the next 7 days</h2>
      <p v-if="!upcoming.length" class="sub">Nothing due this week.</p>
      <ul v-else class="list">
        <li v-for="d in upcoming" :key="d.id">
          <div>
            <strong>{{ d.description }}</strong>
            <div class="small">{{ catName(d.category_id) }}</div>
          </div>
          <div class="when">
            <span class="tag" :class="{ soon: daysFromToday(d.due_date) <= 1 }">{{ dueText(d.due_date) }}</span>
            <span class="small">{{ fmtDate(d.due_date, { day: 'numeric', month: 'short', year: 'numeric' }) }}</span>
          </div>
        </li>
      </ul>
    </div>

    <!-- Matter Catalogue Drawer -->
    <MattersDrawer
      v-if="showMattersDrawer"
      :initial-add-mode="mattersAddMode"
      @close="showMattersDrawer = false"
      @matter-updated="loadDashboardSummary"
    />
  </section>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
}

.interactive-card {
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
  position: relative;
}

.interactive-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--accent);
}

.card-content-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.total-tasks-subtext {
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.25rem;
  cursor: pointer;
  border-radius: 4px;
  display: inline-block;
  width: fit-content;
}

.total-tasks-subtext:hover {
  color: var(--accent);
  text-decoration: underline;
}

.card-action-btn {
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 0.15rem 0.5rem;
  margin-top: 0.35rem;
  cursor: pointer;
  width: fit-content;
  transition: background 0.1s ease;
}

.card-action-btn:hover {
  filter: brightness(0.95);
  border-color: var(--accent);
}
</style>
