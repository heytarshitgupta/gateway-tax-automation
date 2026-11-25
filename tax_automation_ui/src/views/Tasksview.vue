<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { errMessage, useNotify, useList } from '../composables/useApi'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import { day, todayStr, fmtDate } from '../utils/dates'
import PageHeader from '../layouts/PageHeader.vue'
import AlertMessages from '../layouts/AlertMessages.vue'
import FormDrawer from '../layouts/FormDrawer.vue'
import SearchableSelect from '../components/SearchableSelect.vue'

const route = useRoute()
const router = useRouter()

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
const { items: tasks, loading, load } = useList('/tasks/', fail)

const clients = ref([])
const loadingClients = ref(false)
const clientFetchSucceeded = ref(false)

async function loadClients() {
  loadingClients.value = true
  clientFetchSucceeded.value = false
  try {
    const all = []
    let skip = 0
    const limit = 100
    while (true) {
      const res = await api.get('/clients/', { params: { skip, limit } })
      const batch = res.data || []
      all.push(...batch)
      if (batch.length < limit) break
      skip += limit
    }
    const seen = new Set()
    clients.value = all.filter((c) => {
      if (seen.has(c.id)) return false
      seen.add(c.id)
      return true
    })
    clientFetchSucceeded.value = true
  } catch (e) {
    clientFetchSucceeded.value = false
    fail(e)
  } finally {
    loadingClients.value = false
  }
}
onMounted(loadClients)

const { items: staff } = useList('/staff/', fail)

const getClient = (id) => clients.value.find((c) => c.id === id)
const clientName = (id) => getClient(id)?.business_name || `Client #${id}`
const staffName = (id) => staff.value.find((s) => s.id === id)?.name || ''
const isOverdue = (t) => !CLOSED.includes(t.status) && day(t.due_date) && day(t.due_date) < todayStr()

const canEditTask = (t) => {
  if (isHigh.value) return true
  if (isMedium.value && activeStaffId.value && t.staff_id === activeStaffId.value) {
    return true
  }
  return false
}

// ---------- board ----------
const search = ref('')
const clientFilter = ref('') // selected client id (string) or ''
const boardClientSearch = ref('')
const showBoardClientDropdown = ref(false)
const staffFilter = ref('')
const hideClosed = ref(false)

const selectedBoardClient = computed(() => {
  if (!clientFilter.value) return null
  return clients.value.find((c) => c.id === Number(clientFilter.value)) || null
})

const boardMatchingClients = computed(() => {
  const q = boardClientSearch.value.trim().toLowerCase()
  if (!q) return clients.value.slice(0, 30)
  return clients.value.filter((c) => {
    return [c.business_name, c.alias_name, c.mobile_number]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
  }).slice(0, 30)
})

function selectBoardClient(c) {
  if (c === null) {
    clientFilter.value = ''
    boardClientSearch.value = ''
  } else {
    clientFilter.value = String(c.id)
    boardClientSearch.value = c.business_name
  }
  showBoardClientDropdown.value = false
}

function clearBoardClientFilter() {
  clientFilter.value = ''
  boardClientSearch.value = ''
  showBoardClientDropdown.value = false
}

watch(boardClientSearch, (newVal) => {
  if (selectedBoardClient.value && newVal !== selectedBoardClient.value.business_name) {
    clientFilter.value = ''
  }
})

function onDocClick(e) {
  const el = e.target
  if (!el.closest('.board-client-input-wrapper')) {
    showBoardClientDropdown.value = false
  }
  if (!el.closest('.client-search-wrapper')) {
    showClientDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})

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

// ---------- matter selection & custom creation ----------
const matterTypes = ref([])
const loadingMatterTypes = ref(false)
const selectedMatterId = ref(null)
const customMatterName = ref('')
const initialEditingMatterId = ref(null)

async function loadMatterTypes() {
  loadingMatterTypes.value = true
  try {
    const { data } = await api.get('/matter-types/')
    matterTypes.value = Array.isArray(data) ? data : []
  } catch (err) {
    // Graceful fallback
  } finally {
    loadingMatterTypes.value = false
  }
}

const matterOptions = computed(() => {
  const opts = matterTypes.value.map((m) => ({ id: m.id, name: m.name }))
  if (isHigh.value) {
    opts.push({ id: 'others', name: 'Others — Create new matter', isSpecial: true })
  }
  return opts
})

const isHistoricalMatter = computed(() => {
  if (!editingId.value || !form.matter) return false
  return !matterTypes.value.some((m) => m.name.toLowerCase() === form.matter.toLowerCase())
})

// Staff options for SearchableSelect
const staffOptions = computed(() => {
  return staff.value.map((s) => ({
    id: s.id,
    name: s.name,
    alias: s.role,
    subtext: s.access_level,
  }))
})

// Watch router query for navigation from dashboard
watch(
  () => route.query,
  async (newQuery) => {
    if (newQuery.staff_id !== undefined) {
      staffFilter.value = newQuery.staff_id || ''
    }
    if (newQuery.action === 'create') {
      if (isHigh.value) {
        await Promise.all([load(), loadClients(), loadMatterTypes()])
        openForm()
      }
      router.replace({ query: { ...newQuery, action: undefined } }).catch(() => {})
    }
  },
  { immediate: true }
)

// Close open mutation drawers if effective permissions drop during staff preview switching
watch([activeStaffId, isHigh, isLow], ([newId, high, low]) => {
  if (showForm.value) {
    if (low || (!editingId.value && !high)) {
      showForm.value = false
      formError.value = ''
      customMatterName.value = ''
    } else if (editingId.value && !high) {
      const current = tasks.value.find((x) => x.id === editingId.value)
      if (!current || current.staff_id !== newId) {
        showForm.value = false
        formError.value = ''
      } else if (selectedMatterId.value === 'others') {
        selectedMatterId.value = initialEditingMatterId.value || null
        customMatterName.value = ''
      }
    }
  }
})

// ---------- client selection & inline creation ----------
const clientSearchQuery = ref('')
const selectedClient = ref(null)
const showClientDropdown = ref(false)
const highlightedIndex = ref(-1)
const isCreatingInlineClient = ref(false)
const newClientForm = reactive({
  business_name: '',
  alias_name: '',
  mobile_number: '',
  client_type: 'REGULAR',
})

const matchingClients = computed(() => {
  const q = clientSearchQuery.value.trim().toLowerCase()
  if (!q) return clients.value.slice(0, 30)
  return clients.value.filter((c) => {
    return [c.business_name, c.alias_name, c.mobile_number]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
  }).slice(0, 30)
})

function selectExistingClient(client) {
  selectedClient.value = client
  form.client_id = client.id
  clientSearchQuery.value = client.business_name
  showClientDropdown.value = false
  isCreatingInlineClient.value = false
  highlightedIndex.value = -1
}

function clearSelectedClient() {
  selectedClient.value = null
  form.client_id = ''
  clientSearchQuery.value = ''
  showClientDropdown.value = false
  isCreatingInlineClient.value = false
  highlightedIndex.value = -1
}

function onClientSearchInput() {
  if (selectedClient.value && clientSearchQuery.value !== selectedClient.value.business_name) {
    selectedClient.value = null
    form.client_id = ''
  }
  showClientDropdown.value = true
  highlightedIndex.value = -1

  const q = clientSearchQuery.value.trim()
  if (
    q &&
    !editingId.value &&
    isHigh.value &&
    !loadingClients.value &&
    clientFetchSucceeded.value &&
    matchingClients.value.length === 0
  ) {
    startInlineClientCreation()
  }
}

function onSearchKeydown(e) {
  if (!showClientDropdown.value && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    showClientDropdown.value = true
    return
  }
  const list = matchingClients.value
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (!list.length) return
    highlightedIndex.value = (highlightedIndex.value + 1) % list.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (!list.length) return
    highlightedIndex.value = (highlightedIndex.value - 1 + list.length) % list.length
  } else if (e.key === 'Enter') {
    if (showClientDropdown.value && highlightedIndex.value >= 0 && list[highlightedIndex.value]) {
      e.preventDefault()
      selectExistingClient(list[highlightedIndex.value])
    }
  } else if (e.key === 'Escape') {
    showClientDropdown.value = false
  }
}

function startInlineClientCreation() {
  isCreatingInlineClient.value = true
  showClientDropdown.value = false
  selectedClient.value = null
  form.client_id = ''
  newClientForm.business_name = ''
  newClientForm.alias_name = ''
  newClientForm.mobile_number = ''
  newClientForm.client_type = 'REGULAR'
}

function cancelInlineClientCreation() {
  isCreatingInlineClient.value = false
  clientSearchQuery.value = ''
  newClientForm.business_name = ''
  newClientForm.alias_name = ''
  newClientForm.mobile_number = ''
  newClientForm.client_type = 'REGULAR'
}

async function openForm(task = null, status = 'PENDING') {
  if (!task && !isHigh.value) return
  if (task && !canEditTask(task)) return

  await loadMatterTypes()

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

  if (task) {
    const existing = clients.value.find((c) => c.id === task.client_id)
    if (existing) {
      selectedClient.value = existing
      clientSearchQuery.value = existing.business_name
    } else {
      selectedClient.value = { id: task.client_id, business_name: clientName(task.client_id), client_type: 'REGULAR' }
      clientSearchQuery.value = clientName(task.client_id)
    }
    isCreatingInlineClient.value = false
    showClientDropdown.value = false

    // Matter resolution in edit mode
    const matched = matterTypes.value.find((m) => m.name.toLowerCase() === (task.matter || '').toLowerCase())
    if (matched) {
      selectedMatterId.value = matched.id
      initialEditingMatterId.value = matched.id
    } else {
      selectedMatterId.value = null
      initialEditingMatterId.value = null
    }
    customMatterName.value = ''
  } else {
    selectedClient.value = null
    clientSearchQuery.value = ''
    showClientDropdown.value = false
    cancelInlineClientCreation()

    // Matter in add mode
    selectedMatterId.value = null
    initialEditingMatterId.value = null
    customMatterName.value = ''
  }

  showForm.value = true
}

async function save() {
  if (isCreatingInlineClient.value) {
    if (!newClientForm.business_name.trim()) {
      formError.value = 'Client business name is required.'
      return
    }
    if (newClientForm.business_name.trim().length > 150) {
      formError.value = 'Client business name cannot exceed 150 characters.'
      return
    }
    if (newClientForm.mobile_number && newClientForm.mobile_number.trim().length > 20) {
      formError.value = 'Mobile number cannot exceed 20 characters.'
      return
    }
  } else {
    if (!form.client_id) {
      formError.value = 'Choose a client or create a new one.'
      return
    }
  }

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
  const staffId = form.staff_id === '' || form.staff_id === 'unassigned' || form.staff_id === null ? null : Number(form.staff_id)
  const body = {
    staff_id: staffId,
    assigned_staff: staffId ? staffName(staffId) : nul(form.assigned_staff),
    date_assigned: nul(form.date_assigned),
    due_date: nul(form.due_date),
    next_followup_date: nul(form.next_followup_date),
    status: form.status,
    remarks: nul(form.remarks.trim()),
    documents: nul(form.documents.trim()),
  }

  // Matter selection handling
  if (!editingId.value) {
    if (selectedMatterId.value === 'others') {
      const trimmedCustom = customMatterName.value.trim().replace(/\s+/g, ' ')
      if (!trimmedCustom) {
        formError.value = 'Please enter a matter name for Others.'
        saving.value = false
        return
      }
      if (trimmedCustom.length > 200) {
        formError.value = 'Matter name cannot exceed 200 characters.'
        saving.value = false
        return
      }
      body.new_matter = trimmedCustom
    } else if (selectedMatterId.value) {
      body.matter_type_id = Number(selectedMatterId.value)
    } else {
      formError.value = 'Please select a matter from the catalogue or choose Others.'
      saving.value = false
      return
    }
  } else {
    if (selectedMatterId.value === 'others') {
      if (!isHigh.value) {
        formError.value = 'Only HIGH staff can create new matter types.'
        saving.value = false
        return
      }
      const trimmedCustom = customMatterName.value.trim().replace(/\s+/g, ' ')
      if (!trimmedCustom) {
        formError.value = 'Please enter a matter name for Others.'
        saving.value = false
        return
      }
      if (trimmedCustom.length > 200) {
        formError.value = 'Matter name cannot exceed 200 characters.'
        saving.value = false
        return
      }
      body.new_matter = trimmedCustom
    } else if (selectedMatterId.value && selectedMatterId.value !== initialEditingMatterId.value) {
      body.matter_type_id = Number(selectedMatterId.value)
    }
    // If matter was not changed, omit all matter fields to strictly preserve existing historical matter
  }

  if (editingId.value) {
    body.client_id = Number(form.client_id)
  } else {
    if (isCreatingInlineClient.value) {
      body.new_client = {
        business_name: newClientForm.business_name.trim(),
        alias_name: newClientForm.alias_name.trim() || null,
        mobile_number: newClientForm.mobile_number.trim() || null,
        client_type: newClientForm.client_type || 'REGULAR',
      }
    } else {
      body.client_id = Number(form.client_id)
    }
  }

  try {
    if (editingId.value) await api.patch(`/tasks/${editingId.value}`, body)
    else await api.post('/tasks/', body)
    flash(editingId.value ? 'Task updated' : 'Task added')
    showForm.value = false
    await Promise.all([load(), loadClients(), loadMatterTypes()])
  } catch (e) {
    if (e.response?.status === 409 && (body.new_matter || selectedMatterId.value === 'others')) {
      formError.value = 'A matter with this name already exists in the catalogue. Please select it from the catalogue or enter a unique name.'
      await loadMatterTypes()
    } else {
      formError.value = errMessage(e)
    }
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
      <div class="board-client-filter">
        <div class="board-client-input-wrapper">
          <input
            v-model="boardClientSearch"
            @focus="showBoardClientDropdown = true"
            @input="showBoardClientDropdown = true"
            placeholder="All clients (type to filter)"
            aria-label="Client filter"
            class="client-filter-input"
            autocomplete="off"
          />
          <button
            v-if="clientFilter || boardClientSearch"
            type="button"
            class="mini board-filter-clear-btn"
            @click="clearBoardClientFilter"
            title="Clear client filter"
            aria-label="Clear client filter"
          >
            ✕
          </button>
          <div v-if="showBoardClientDropdown" class="board-client-dropdown">
            <div
              class="board-dropdown-item"
              :class="{ active: !clientFilter }"
              @mousedown.prevent="selectBoardClient(null)"
            >
              <strong>All clients</strong>
            </div>
            <div
              v-for="c in boardMatchingClients"
              :key="c.id"
              class="board-dropdown-item"
              :class="{ active: clientFilter === String(c.id) }"
              @mousedown.prevent="selectBoardClient(c)"
            >
              <div class="board-dropdown-item-main">
                <span class="client-id-badge">#{{ c.id }}</span>
                <strong>{{ c.business_name }}</strong>
                <span class="muted-text">({{ c.mobile_number || 'No mobile' }})</span>
                <span v-if="c.client_type === 'TEMP'" class="chip type-chip temp">Temp</span>
                <span v-else class="chip type-chip regular">Regular</span>
              </div>
              <div v-if="c.alias_name" class="small muted-text">
                Alias: {{ c.alias_name }}
              </div>
            </div>
            <div v-if="!boardMatchingClients.length" class="dropdown-no-results">
              <p class="small muted-text">No matching clients found.</p>
            </div>
          </div>
        </div>
      </div>
      <div class="board-staff-filter" style="min-width: 170px;">
        <SearchableSelect
          v-model="staffFilter"
          :options="staffOptions"
          placeholder="All staff"
          includeAll
          allLabel="All staff"
          includeUnassigned
          unassignedLabel="Unassigned"
          ariaLabel="Staff filter"
        />
      </div>
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
          <div class="card-client">
            {{ clientName(t.client_id) }}
            <span v-if="getClient(t.client_id)?.client_type === 'TEMP'" class="chip type-chip temp">Temp</span>
          </div>
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
      <!-- Selected Client display -->
      <div v-if="selectedClient && !isCreatingInlineClient" class="selected-client-card">
        <div class="selected-client-info">
          <div class="client-title-row">
            <strong>{{ selectedClient.business_name }}</strong>
            <span v-if="selectedClient.client_type === 'TEMP'" class="chip type-chip temp">Temp</span>
            <span v-else class="chip type-chip regular">Regular</span>
            <span v-if="selectedClient.alias_name" class="chip alias-chip">Alias: {{ selectedClient.alias_name }}</span>
          </div>
          <div class="small muted-text">
            <span>{{ selectedClient.mobile_number || 'No mobile' }}</span>
          </div>
        </div>
        <button
          v-if="isHigh && !editingId"
          type="button"
          class="mini"
          @click="clearSelectedClient"
          aria-label="Change client"
        >
          ✕ Change
        </button>
        <button
          v-else-if="isHigh && editingId"
          type="button"
          class="mini"
          @click="clearSelectedClient"
          aria-label="Reassign client"
        >
          Change client
        </button>
      </div>

      <!-- Searchable autocomplete input when no client is selected and not creating inline -->
      <div v-else-if="!isCreatingInlineClient" class="client-search-wrapper">
        <label>Client *
          <input
            v-model="clientSearchQuery"
            @input="onClientSearchInput"
            @focus="showClientDropdown = true"
            @keydown="onSearchKeydown"
            placeholder="Search by client name, alias, or mobile..."
            :disabled="!isHigh"
            autocomplete="off"
            aria-label="Search client"
          />
        </label>

        <!-- Dropdown menu -->
        <div v-if="showClientDropdown" class="autocomplete-dropdown">
          <div
            v-for="(c, idx) in matchingClients"
            :key="c.id"
            class="dropdown-item"
            :class="{ active: idx === highlightedIndex }"
            @mousedown.prevent="selectExistingClient(c)"
          >
            <div class="dropdown-item-main">
              <strong>{{ c.business_name }}</strong>
              <span class="muted-text">({{ c.mobile_number || 'No mobile' }})</span>
              <span v-if="c.client_type === 'TEMP'" class="chip type-chip temp">Temp</span>
              <span v-else class="chip type-chip regular">Regular</span>
            </div>
            <div v-if="c.alias_name" class="small muted-text">
              Alias: {{ c.alias_name }}
            </div>
          </div>

          <div v-if="!matchingClients.length" class="dropdown-no-results">
            <p class="small muted-text">No matching clients found.</p>
          </div>

          <!-- Option to create new client inline (HIGH only, and not during edit) -->
          <div v-if="isHigh && !editingId" class="dropdown-create-action" @mousedown.prevent="startInlineClientCreation">
            <button type="button" class="btn-create-inline" @click="startInlineClientCreation">
              + New client
            </button>
          </div>
        </div>
      </div>

      <!-- Inline Client Creation Form -->
      <div v-else class="inline-client-box">
        <div class="inline-client-header">
          <span class="inline-title">New Client Details</span>
          <button type="button" class="mini" @click="cancelInlineClientCreation">Cancel & Search</button>
        </div>
        <div class="two">
          <label>Client business name *
            <input v-model="newClientForm.business_name" required maxlength="150" placeholder="e.g. Acme Corp" />
          </label>
          <label>Alias name (optional)
            <input v-model="newClientForm.alias_name" maxlength="150" placeholder="e.g. Acme" />
          </label>
        </div>
        <div class="two">
          <label>Mobile number (optional)
            <input v-model="newClientForm.mobile_number" maxlength="20" placeholder="e.g. 9876543210" />
          </label>
          <div class="client-type-field">
            <label style="font-size: 0.88rem; font-weight: 600; color: var(--muted); margin-bottom: 0.25rem; display: block;">Client type</label>
            <div style="display: flex; align-items: center; gap: 0.6rem; margin-top: 0.25rem;">
              <button
                type="button"
                class="pill"
                :class="newClientForm.client_type === 'REGULAR' ? 'on' : 'off'"
                @click="newClientForm.client_type = newClientForm.client_type === 'REGULAR' ? 'TEMP' : 'REGULAR'"
                :title="newClientForm.client_type === 'REGULAR' ? 'Click to switch to Temp' : 'Click to switch to Regular'"
              >
                {{ newClientForm.client_type === 'REGULAR' ? 'Regular' : 'Temp' }}
              </button>
              <span class="small muted-text">{{ newClientForm.client_type === 'REGULAR' ? 'Regular client' : 'Temp client' }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="form-field-group">
        <div style="display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.88rem; font-weight: 600; color: var(--muted);">
          <span>Matter *</span>
          <div v-if="editingId && isHistoricalMatter && selectedMatterId !== 'others'" class="small muted-text" style="margin-bottom: 0.25rem;">
            Current historical matter: <strong>{{ form.matter }}</strong>
          </div>
          <SearchableSelect
            v-model="selectedMatterId"
            class="task-matter-select"
            :options="matterOptions"
            :placeholder="editingId && isHistoricalMatter ? form.matter : 'Select a matter...'"
            searchPlaceholder="Search available matters..."
            :loading="loadingMatterTypes"
            ariaLabel="Matter"
            aria-label="Matter"
          />
        </div>
        <div v-if="selectedMatterId === 'others'" class="custom-matter-box" style="margin-top: 0.5rem; background: var(--sunken); padding: 0.6rem; border-radius: 6px;">
          <label style="display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.88rem; font-weight: 600; color: var(--muted);">
            New matter name *
            <input
              v-model="customMatterName"
              type="text"
              class="custom-matter-input"
              maxlength="200"
              placeholder="e.g. Custom GST Advisory"
              required
              autocomplete="off"
              aria-label="New matter name"
            />
          </label>
          <button type="button" class="mini" style="margin-top: 0.35rem;" @click="selectedMatterId = initialEditingMatterId || null; customMatterName = ''">
            Cancel new matter
          </button>
        </div>
      </div>
      <div class="two">
        <label>Assigned to
          <SearchableSelect
            v-model="form.staff_id"
            :options="staffOptions"
            placeholder="Unassigned"
            includeUnassigned
            unassignedLabel="Unassigned"
            :disabled="!isHigh"
            ariaLabel="Assigned staff"
          />
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

<style scoped>
.type-chip {
  margin-left: 0.4rem;
  font-size: 0.75rem;
  font-weight: 600;
  vertical-align: middle;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
}
.type-chip.regular {
  background: var(--ok-soft);
  color: var(--ok);
  border: 1px solid var(--line);
}
.type-chip.temp {
  background: var(--warn-soft);
  color: var(--warn);
  border: 1px solid var(--line);
}

.alias-chip {
  margin-left: 0.4rem;
  font-size: 0.78rem;
  font-weight: 500;
  vertical-align: middle;
  background: var(--sunken);
  color: var(--muted);
  border: 1px solid var(--line);
}

.selected-client-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0.8rem;
  background: var(--paper);
  border: 1px solid var(--accent);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}

.selected-client-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.client-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.client-search-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.autocomplete-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 30;
  max-height: 220px;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  margin-top: 0.25rem;
}

.dropdown-item {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  transition: background 0.15s ease;
}

.dropdown-item:last-child {
  border-bottom: none;
}

.dropdown-item:hover, .dropdown-item.active {
  background: var(--sunken);
}

.dropdown-item-main {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.dropdown-no-results {
  padding: 0.6rem 0.75rem;
  text-align: center;
}

.dropdown-create-action {
  padding: 0.4rem;
  background: var(--paper);
  border-top: 1px solid var(--line);
}

.btn-create-inline {
  width: 100%;
  padding: 0.4rem 0.6rem;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent);
  background: var(--surface);
  border: 1px dashed var(--accent);
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
}

.btn-create-inline:hover {
  background: var(--accent-soft);
}

.inline-client-box {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.8rem;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: var(--paper);
}

.inline-client-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.inline-title {
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--accent);
}

.board-client-filter {
  position: relative;
  display: flex;
  align-items: center;
}

.board-client-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.client-filter-input {
  min-width: 220px;
  padding-right: 1.8rem;
}

.board-filter-clear-btn {
  position: absolute;
  right: 0.3rem;
  padding: 0.1rem 0.35rem;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--muted);
}

.board-client-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 280px;
  max-width: 380px;
  max-height: 250px;
  overflow-y: auto;
  z-index: 40;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  margin-top: 0.25rem;
}

.board-dropdown-item {
  padding: 0.45rem 0.7rem;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s ease;
}

.board-dropdown-item:last-child {
  border-bottom: none;
}

.board-dropdown-item:hover, .board-dropdown-item.active {
  background: var(--sunken);
}

.board-dropdown-item-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.client-id-badge {
  font-size: 0.72rem;
  font-family: monospace;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  background: var(--sunken);
  color: var(--muted);
  border: 1px solid var(--line);
}
</style>
