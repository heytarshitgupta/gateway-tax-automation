<script setup>
import { ref, computed } from 'vue'
import api from '../api'
import { todayStr, day, daysFromToday, fmtDate } from '../utils/dates'
import PageHeader from '../layouts/PageHeader.vue'
import StatCard from '../layouts/StatCard.vue'
import { errMessage, useList } from '../composables/useApi'

// Set this to the real path of your reminder-job endpoint (see /docs).
const RUN_JOB_PATH = '/automation/run-reminders'

// ---------- data ----------
const problems = ref([])
// const miss = (name) => () => problems.value.push(`Could not load ${name}.`)
const miss = (name) => (e) => problems.value.push(`Could not load ${name}: ${errMessage(e)}`)
const lists = [
  useList('/clients/', miss('clients')),
  useList('/messages/', miss('messages')),
  useList('/compliance-dates/', miss('compliance dates')),
  useList('/categories/', miss('categories')),
]
const [clients, messages, dates, categories] = lists.map((l) => l.items)
const loading = computed(() => lists.some((l) => l.loading.value))

// The messages table may name its timestamp differently; the first one found is used.
const msgDay = (m) => day(m.sent_at || m.created_at || m.timestamp || m.updated_at)
const catName = (id) => categories.value.find((c) => c.id === id)?.name || ''

const upcoming = computed(() =>
  dates.value
    .filter((d) => d.due_date && daysFromToday(d.due_date) >= 0 && daysFromToday(d.due_date) <= 7)
    .sort((a, b) => day(a.due_date).localeCompare(day(b.due_date)))
)

const cards = computed(() => {
  const today = todayStr()
  const sent = messages.value.filter((m) => ['SENT', 'DELIVERED', 'READ'].includes(m.status) && msgDay(m) === today)
  const failed = messages.value.filter((m) => m.status === 'FAILED' && msgDay(m) === today)
  const active = clients.value.filter((c) => c.is_active).length
  return [
    { label: 'Total clients', value: clients.value.length, icon: '👥', tone: 'blue' },
    { label: 'Active clients', value: active, icon: '✅', tone: 'green' },
    { label: 'Inactive clients', value: clients.value.length - active, icon: '⏸️', tone: 'grey' },
    { label: 'Messages sent today', value: sent.length, icon: '💬', tone: 'mint' },
    { label: 'Failed today', value: failed.length, icon: '⚠️', tone: 'red' },
    { label: 'Due within 7 days', value: upcoming.value.length, icon: '🗓️', tone: 'amber' },
  ]
})

const dueText = (d) => ['Today', 'Tomorrow'][daysFromToday(d)] ?? `In ${daysFromToday(d)} days`

// ---------- reminder job ----------
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
    lists.forEach((l) => l.load())
  } catch (e) {
    const s = e?.response?.status
    jobError.value = [404, 405].includes(s)
      ? `The API has no ${RUN_JOB_PATH} endpoint (HTTP ${s}). Find the reminder route in /docs and update RUN_JOB_PATH in DashboardView.vue.`
      : e?.response?.data?.detail || e.message || 'The reminder job failed.'
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section>
    <PageHeader title="Dashboard" subtitle="Overview of client engagement and WhatsApp automation performance." />

    <p v-for="p in problems" :key="p" class="banner error" role="alert">{{ p }}</p>

    <div class="cards" :aria-busy="loading">
      <StatCard v-for="c in cards" :key="c.label" v-bind="c" :value="loading ? '…' : c.value" />
    </div>

    <div class="panel engine">
      <div>
        <h2>Automation engine</h2>
        <p>
          The scheduler runs automatically every day at 09:00 to send GST/TDS reminders for compliance
          dates due in 7, 3, and 1 day(s). You can also trigger it manually here for testing or demos.
        </p>
      </div>
      <button class="run" :disabled="running" @click="runJob">{{ running ? 'Running…' : 'Run reminder job now' }}</button>
    </div>
    <p v-if="jobResult" class="banner ok" role="status" style="margin-top: 1rem">{{ jobResult }}</p>
    <p v-if="jobError" class="banner error" role="alert" style="margin-top: 1rem">{{ jobError }}</p>

    <div class="panel">
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
  </section>
</template>