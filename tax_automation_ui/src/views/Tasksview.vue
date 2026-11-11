<script setup>
import { ref, reactive, computed } from 'vue'
import api from '../api'
import { errMessage, useNotify, useList } from '../composables/useApi'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import { day, todayStr, fmtDate } from '../utils/dates'
import PageHeader from '../layouts/PageHeader.vue'
import AlertMessages from '../layouts/AlertMessages.vue'
import FormDrawer from '../layouts/FormDrawer.vue'

const STATUSES = [
  { key: 'PENDING', label: 'Pending' },
  { key: 'IN_PROGRESS', label: 'In progress' },
  { key: 'WAITING_DOCUMENTS', label: 'Waiting for documents' },
  { key: 'ON_HOLD', label: 'On hold' },
  { key: 'UNDER_REVIEW', label: 'Under review' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'CANCELLED', label: 'Cancelled' },
]
const CLOSED = ['COMPLETED', 'CANCELLED']
const statusLabel = (k) => STATUSES.find((s) => s.key === k)?.label
const nul = (v) => (v === '' || v === undefined ? null : v)

// ---------- data ----------
const { error, toast, flash, fail } = useNotify()
const { activeStaffId, isHigh, isMedium, isLow } = useCurrentStaff()
const { items: tasks, loading, load } = useList('/tasks', fail)
const { items: clients } = useList('/clients', fail)
const { items: staff } = useList('/staff', fail)

const clientName = (id) => clients.value.find((c) => c.id === id)?.business_name || `Client #${id}`
const staffName = (id) => staff.value.find((s) => s.id === id)?.name || ''
const isOverdue = (t) => !CLOSED.includes(t.status) && day(t.due_date) && day(t.due_date) < todayStr()

const canEditTask = (t) => {
  if (isHigh.value) return true
  if ((isMedium.value || isLow.value) && activeStaffId.value && t.staff_id === activeStaffId.value) {
    return true
  }
  return false
}

// ---------- board ----------
const search = ref('')
const clientFilter = ref('')
const staffFilter = ref('')
const hideClosed = ref(false)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return tasks.value.filter((t) =>
    (!clientFilter.value || t.client_id === Number(clientFilter.value)) &&
    (!staffFilter.value || t.staff_id === Number(staffFilter.value)) &&
    (!q || [t.matter, t.remarks, clientName(t.client_id)].some((v) => String(v ?? '').toLowerCase().includes(q)))
  )
})
const columns = computed(() =>
  STATUSES.filter((s) => !(hideClosed.value && CLOSED.includes(s.key))).map((s) => ({
    ...s,
    items: filtered.value
      .filter((t) => t.status === s.key)
      .sort((a, b) => (day(a.due_date) || '9999').localeCompare(day(b.due_date) || '9999')),
  }))
)
const overdueCount = computed(() => filtered.value.filter(isOverdue).length)
const subtitle = computed(() => `${filtered.value.length} tasks` + (overdueCount.value ? ` · ${overdueCount.value} overdue` : ''))

// ---------- move (drag or dropdown) ----------
const toBody = (t, over = {}) => ({
  client_id: t.client_id,
  staff_id: t.staff_id ?? null,
  matter: t.matter,
  assigned_staff: t.assigned_staff ?? null,
  date_assigned: nul(day(t.date_assigned)),
  due_date: nul(day(t.due_date)),
  next_followup_date: nul(day(t.next_followup_date)),
  status: t.status,
  remarks: t.remarks ?? null,
  documents: t.documents ?? null,
  ...over,
})

async function moveTo(t, status) {
  if (!canEditTask(t)) {
    fail({ message: 'You can only update matters assigned to you.' })
    return
  }
  if (t.status === status) return
  const old = t.status
  t.status = status // optimistic
  try {
    await api.patch(`/tasks/${t.id}`, toBody(t, { status }))
    flash('Moved to ' + statusLabel(status))
  } catch (e) {
    t.status = old
    fail(e)
  }
}
const dragId = ref(null)
const dragOver = ref('')
function onDrop(status) {
  const t = tasks.value.find((x) => x.id === dragId.value)
  dragId.value = dragOver.value = null
  if (t && canEditTask(t)) moveTo(t, status)
}

// ---------- form ----------
const blankForm = (status = 'PENDING') => ({
  client_id: '', staff_id: '', matter: '', date_assigned: todayStr(), due_date: '',
  next_followup_date: '', status, remarks: '', documents: '', assigned_staff: '',
})
const form = reactive(blankForm())
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')

function openForm(task = null, status = 'PENDING') {
  if (!task && !isHigh.value) return
  if (task && !canEditTask(task)) return

  editingId.value = task?.id ?? null
  Object.assign(form, task
    ? {
        ...blankForm(), ...task,
        client_id: task.client_id ?? '', staff_id: task.staff_id ?? '',
        date_assigned: day(task.date_assigned), due_date: day(task.due_date),
        next_followup_date: day(task.next_followup_date),
        remarks: task.remarks ?? '', documents: task.documents ?? '', assigned_staff: task.assigned_staff ?? '',
      }
    : blankForm(status))
  formError.value = ''
  showForm.value = true
}

async function save() {
  if (!form.client_id || !form.matter.trim()) return (formError.value = 'Choose a client and describe the matter.')
  if (!editingId.value && !isHigh.value) {
    formError.value = 'Creating matters requires HIGH access.'
    return
  }
  if (editingId.value) {
    const current = tasks.value.find((x) => x.id === editingId.value)
    if (current && !canEditTask(current)) {
      formError.value = 'You can only edit matters assigned to you.'
      return
    }
  }

  saving.value = true
  formError.value = ''
  const staffId = form.staff_id === '' ? null : Number(form.staff_id)
  const body = {
    client_id: Number(form.client_id),
    staff_id: staffId,
    matter: form.matter.trim(),
    assigned_staff: staffId ? staffName(staffId) : nul(form.assigned_staff), // keeps the name text in step
    date_assigned: nul(form.date_assigned),
    due_date: nul(form.due_date),
    next_followup_date: nul(form.next_followup_date),
    status: form.status,
    remarks: nul(form.remarks.trim()),
    documents: nul(form.documents.trim()),
  }
  try {
    if (editingId.value) await api.patch(`/tasks/${editingId.value}`, body)
    else await api.post('/tasks', body)
    flash(editingId.value ? 'Task updated' : 'Task added')
    showForm.value = false
    await load()
  } catch (e) {
    formError.value = errMessage(e)
  } finally {
    saving.value = false
  }
}
async function remove(t) {
  if (!isHigh.value) return
  if (!confirm(`Delete task "${t.matter}"? This cannot be undone.`)) return
  try {
    await api.delete(`/tasks/${t.id}`)
    flash('Task deleted')
    await load()
  } catch (e) {
    fail(e)
  }
}
</script>

<template>
  <section>
    <PageHeader title="Tasks" :subtitle="subtitle">
      <button v-if="isHigh" class="btn primary" @click="openForm()">Add task</button>
    </PageHeader>

    <div class="filters">
      <input v-model="search" type="search" placeholder="Search matter, remarks or client" aria-label="Search tasks" />
      <select v-model="clientFilter" aria-label="Client filter">
        <option value="">All clients</option>
        <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.business_name }}</option>
      </select>
      <select v-model="staffFilter" aria-label="Staff filter">
        <option value="">All staff</option>
        <option v-for="s in staff" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <label class="inline"><input type="checkbox" v-model="hideClosed" /> Hide completed and cancelled</label>
    </div>

    <AlertMessages :error="error" :toast="toast" />
    <p v-if="loading" class="sub">Loading tasks…</p>

    <div class="board">
      <div v-for="col in columns" :key="col.key" class="col" :class="{ over: dragOver === col.key }"
        @dragover.prevent="dragOver = col.key" @dragleave="dragOver = ''" @drop.prevent="onDrop(col.key)">
        <div class="col-head">
          <span class="dot" :class="col.key"></span>
          <h2>{{ col.label }}</h2>
          <span class="count">{{ col.items.length }}</span>
          <button v-if="isHigh" class="mini" :aria-label="`Add task to ${col.label}`" @click="openForm(null, col.key)">+</button>
        </div>

        <p v-if="!col.items.length" class="none">Nothing here.<span v-if="isHigh"> Drag a task in or press +.</span></p>

        <article v-for="t in col.items" :key="t.id" class="card" :class="{ late: isOverdue(t) }"
          :draggable="canEditTask(t)" @dragstart="dragId = t.id" @dragend="dragId = dragOver = null">
          <div class="card-client">{{ clientName(t.client_id) }}</div>
          <h3>{{ t.matter }}</h3>
          <div class="meta">
            <span :class="{ 'late-text': isOverdue(t) }">Due {{ fmtDate(t.due_date) }}</span>
            <span v-if="t.next_followup_date">Follow up {{ fmtDate(t.next_followup_date) }}</span>
          </div>
          <div v-if="staffName(t.staff_id) || t.assigned_staff" class="meta">
            {{ staffName(t.staff_id) || t.assigned_staff }}
          </div>
          <p v-if="t.remarks" class="remarks">{{ t.remarks }}</p>
          <div class="card-actions">
            <select :value="t.status" :disabled="!canEditTask(t)" @change="moveTo(t, $event.target.value)" aria-label="Change status">
              <option v-for="s in STATUSES" :key="s.key" :value="s.key">{{ s.label }}</option>
            </select>
            <button v-if="canEditTask(t)" class="mini" @click="openForm(t)">Edit</button>
            <button v-if="isHigh" class="mini danger" @click="remove(t)">Delete</button>
          </div>
        </article>
      </div>
    </div>

    <FormDrawer v-if="showForm" :title="editingId ? 'Edit task' : 'Add task'" :error="formError"
      :saving="saving" :submit-label="editingId ? 'Save changes' : 'Add task'"
      @close="showForm = false" @submit="save">
      <label>Client *
        <select v-model="form.client_id" :disabled="!isHigh" required>
          <option value="" disabled>Choose a client</option>
          <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.business_name }}</option>
        </select>
      </label>
      <label>Matter *<input v-model="form.matter" required placeholder="e.g. GST return for October" /></label>
      <div class="two">
        <label>Assigned to
          <select v-model="form.staff_id" :disabled="!isHigh">
            <option value="">Unassigned</option>
            <option v-for="s in staff" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
        <label>Status
          <select v-model="form.status">
            <option v-for="s in STATUSES" :key="s.key" :value="s.key">{{ s.label }}</option>
          </select>
        </label>
      </div>
      <div class="three">
        <label>Date assigned<input type="date" v-model="form.date_assigned" /></label>
        <label>Due date<input type="date" v-model="form.due_date" /></label>
        <label>Next follow-up<input type="date" v-model="form.next_followup_date" /></label>
      </div>
      <label>Documents received or needed<textarea v-model="form.documents" rows="2"></textarea></label>
      <label>Remarks<textarea v-model="form.remarks" rows="3"></textarea></label>
    </FormDrawer>
  </section>
</template>
