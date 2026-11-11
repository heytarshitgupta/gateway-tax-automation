<script setup>
import { ref, reactive, computed, watch } from 'vue'
import api from '../api'
import { errMessage, useNotify, useList } from '../composables/useApi'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import PageHeader from '../layouts/PageHeader.vue'
import AlertMessages from '../layouts/AlertMessages.vue'
import FormDrawer from '../layouts/FormDrawer.vue'

const TEXT_FIELDS = [
  ['contact_name', 'Contact person'],
  ['mobile_number', 'Mobile number'],
  ['gst_details', 'GST number'],
  ['pan_details', 'PAN'],
  ['tan_details', 'TAN'],
]

// ---------- data & permissions ----------
const { error, toast, flash, fail } = useNotify()
const { isHigh, isMedium } = useCurrentStaff()
const canAddClient = computed(() => isHigh.value || isMedium.value)
const canManageGroups = computed(() => isHigh.value || isMedium.value)
const canViewClientActions = computed(() => isHigh.value || isMedium.value)

const search = ref('')
const activeFilter = ref('all') // all | active | inactive
const categoryFilter = ref('')
const groupFilter = ref('') // '' (All groups) | 'ungrouped' | String(group_id)

const { items: clients, loading, load } = useList('/clients', fail, () =>
  activeFilter.value === 'all' ? {} : { is_active: activeFilter.value === 'active' }
)
const { items: categories } = useList('/categories', fail)
const { items: staff } = useList('/staff', fail)
const { items: groups, loading: groupsLoading, load: loadGroups } = useList('/groups', fail)

// Load matters using existing useList composable with non-blocking error handling
const taskWarning = ref('')
const onTaskError = () => {
  taskWarning.value = 'Notice: Matter data could not be loaded. Matter-based search is temporarily unavailable.'
}
const { items: tasks, loading: tasksLoading, load: loadTasks } = useList('/tasks', onTaskError)

// Client-to-matters reactive lookup
const clientMattersMap = computed(() => {
  const map = new Map()
  for (const task of tasks.value || []) {
    const clientId = Number(task.client_id)
    if (!Number.isFinite(clientId)) continue
    if (!map.has(clientId)) {
      map.set(clientId, [])
    }
    map.get(clientId).push(task)
  }
  return map
})

// Matching matter badge helper
const matchingMatterBadge = (clientId) => {
  const q = search.value.trim().toLowerCase()
  if (!q) return null

  const clientTasks = clientMattersMap.value.get(Number(clientId)) || []
  const matches = []

  for (const t of clientTasks) {
    const title = String(t.matter || '').toLowerCase()
    const remarks = String(t.remarks || '').toLowerCase()
    if (title.includes(q) || remarks.includes(q)) {
      if (t.matter && !matches.includes(t.matter)) {
        matches.push(t.matter)
      }
    }
  }

  if (!matches.length) return null
  if (matches.length === 1) {
    return matches[0]
  }
  return `${matches[0]} (+${matches.length - 1} more)`
}

const groupMap = computed(() => {
  const map = new Map()
  for (const g of groups.value || []) {
    map.set(g.id, g.name)
  }
  return map
})

const getGroupName = (id) => (id ? groupMap.value.get(id) || '' : '')

// Reset group filter if active group is deleted
watch(groups, (newGroups) => {
  if (groupFilter.value && groupFilter.value !== 'ungrouped') {
    const exists = (newGroups || []).some((g) => String(g.id) === groupFilter.value)
    if (!exists) groupFilter.value = ''
  }
})

const staffName = (id) => staff.value.find((s) => s.id === id)?.name || '—'

const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  const cat = Number(categoryFilter.value)
  const gf = groupFilter.value
  return clients.value.filter((c) => {
    if (cat && c.category_id !== cat && !(c.categories || []).some((x) => x.id === cat)) return false
    if (gf === 'ungrouped' && c.group_id != null) return false
    if (gf && gf !== 'ungrouped' && String(c.group_id) !== gf) return false
    if (!q) return true

    // 1. Existing client fields match
    const clientMatch = [c.business_name, c.alias_name, ...TEXT_FIELDS.map(([k]) => c[k])]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
    if (clientMatch) return true

    // 2. Associated matters/tasks match (matter title or remarks)
    const clientTasks = clientMattersMap.value.get(Number(c.id)) || []
    return clientTasks.some((task) => {
      const title = String(task.matter || '').toLowerCase()
      const remarks = String(task.remarks || '').toLowerCase()
      return title.includes(q) || remarks.includes(q)
    })
  })
})
const subtitle = computed(() => `${visible.value.length} of ${clients.value.length} shown`)

// ---------- client form ----------
const blankForm = () => ({
  business_name: '', alias_name: '', contact_name: '', mobile_number: '', gst_details: '', pan_details: '', tan_details: '',
  category_id: '', assigned_staff_id: '', is_active: true, category_ids: [],
})
const fromClient = (c) => ({
  ...Object.fromEntries(['business_name', ...TEXT_FIELDS.map(([k]) => k)].map((k) => [k, c[k] ?? ''])),
  alias_name: c.alias_name ?? '',
  category_id: c.category_id ?? '',
  assigned_staff_id: c.assigned_staff_id ?? '',
  is_active: !!c.is_active,
  category_ids: (c.categories || []).map((x) => x.id),
})
const toBody = (f) => ({
  business_name: f.business_name.trim(),
  alias_name: f.alias_name?.trim() || null,
  ...Object.fromEntries(TEXT_FIELDS.map(([k]) => [k, f[k].trim() || null])),
  category_id: f.category_id === '' ? null : Number(f.category_id),
  assigned_staff_id: f.assigned_staff_id === '' ? null : Number(f.assigned_staff_id),
  is_active: f.is_active,
  category_ids: f.category_ids,
})

const form = reactive(blankForm())
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')

// Family group state inside Edit Client drawer
const clientFormGroupId = ref(null)
const initialClientGroupId = ref(null)
const initialFormJson = ref('')
const editGroupSearch = ref('')
const showCreateGroupInEdit = ref(false)
const newGroupNameInEdit = ref('')
const creatingGroupInEdit = ref(false)

const filteredGroupsForEdit = computed(() => {
  const q = editGroupSearch.value.trim().toLowerCase()
  if (!q) return groups.value || []
  return (groups.value || []).filter((g) => g.name.toLowerCase().includes(q))
})

const groupChangeWarning = computed(() => {
  if (!editingId.value || clientFormGroupId.value === initialClientGroupId.value) return ''
  const clientName = form.business_name || 'This client'
  if (clientFormGroupId.value && initialClientGroupId.value) {
    const oldName = getGroupName(initialClientGroupId.value) || 'another group'
    const newName = getGroupName(clientFormGroupId.value) || 'new group'
    return `Note: ${clientName} will be moved from "${oldName}" to "${newName}" when saved.`
  }
  if (!clientFormGroupId.value && initialClientGroupId.value) {
    const oldName = getGroupName(initialClientGroupId.value) || 'current group'
    return `Note: ${clientName} will be removed from "${oldName}" (ungrouped) when saved.`
  }
  if (clientFormGroupId.value && !initialClientGroupId.value) {
    const newName = getGroupName(clientFormGroupId.value) || 'selected group'
    return `Note: ${clientName} will be assigned to "${newName}" when saved.`
  }
  return ''
})

function openForm(client = null) {
  if (client && !isHigh.value) return
  if (!client && !canAddClient.value) return
  editingId.value = client?.id ?? null
  Object.assign(form, client ? fromClient(client) : blankForm())
  initialFormJson.value = JSON.stringify(toBody(form))
  clientFormGroupId.value = client?.group_id ?? null
  initialClientGroupId.value = client?.group_id ?? null
  editGroupSearch.value = ''
  showCreateGroupInEdit.value = false
  newGroupNameInEdit.value = ''
  formError.value = ''
  showForm.value = true
}

async function createGroupInEdit() {
  const trimmed = newGroupNameInEdit.value.trim()
  if (!trimmed) {
    formError.value = 'Group name is required.'
    return
  }
  if (trimmed.length > 100) {
    formError.value = 'Group name cannot exceed 100 characters.'
    return
  }
  creatingGroupInEdit.value = true
  formError.value = ''
  let newGroup = null
  try {
    const res = await api.post('/groups/', { name: trimmed })
    newGroup = res.data
    await loadGroups()
  } catch (e) {
    formError.value = errMessage(e)
    creatingGroupInEdit.value = false
    return
  }

  // Assign current client if editing
  if (editingId.value && newGroup) {
    try {
      await api.post(`/groups/${newGroup.id}/clients/${editingId.value}`)
      clientFormGroupId.value = newGroup.id
      initialClientGroupId.value = newGroup.id
      flash(`Group "${newGroup.name}" created and assigned`)
      showCreateGroupInEdit.value = false
      newGroupNameInEdit.value = ''
      await Promise.all([load(), loadGroups()])
    } catch (e) {
      clientFormGroupId.value = newGroup.id
      formError.value = `Group created, but assigning client failed: ${errMessage(e)}`
      showCreateGroupInEdit.value = false
      newGroupNameInEdit.value = ''
      await Promise.all([load(), loadGroups()])
    }
  } else if (newGroup) {
    clientFormGroupId.value = newGroup.id
    flash(`Group "${newGroup.name}" created`)
    showCreateGroupInEdit.value = false
    newGroupNameInEdit.value = ''
  }
  creatingGroupInEdit.value = false
}

async function save() {
  if (!form.business_name.trim()) return (formError.value = 'Business name is required.')
  if (editingId.value && !isHigh.value) {
    formError.value = 'Editing clients requires HIGH access.'
    return
  }
  if (!editingId.value && !canAddClient.value) {
    formError.value = 'Adding clients requires HIGH or MEDIUM access.'
    return
  }

  saving.value = true
  formError.value = ''

  const clientPayload = toBody(form)
  const clientPayloadStr = JSON.stringify(clientPayload)
  const clientFieldsChanged = !editingId.value || clientPayloadStr !== initialFormJson.value

  let savedClient = null
  if (clientFieldsChanged) {
    try {
      if (editingId.value) {
        const res = await api.patch(`/clients/${editingId.value}`, clientPayload)
        savedClient = res.data
        initialFormJson.value = clientPayloadStr
      } else {
        const res = await api.post('/clients', clientPayload)
        savedClient = res.data
        initialFormJson.value = JSON.stringify(toBody(fromClient(savedClient)))
      }
    } catch (e) {
      formError.value = errMessage(e)
      saving.value = false
      return
    }
  }

  // Handle group assignment separately via dedicated group endpoints (never PATCH /clients)
  const clientId = editingId.value || savedClient?.id
  const groupChanged = clientFormGroupId.value !== initialClientGroupId.value

  if (clientId && groupChanged && canManageGroups.value) {
    try {
      if (clientFormGroupId.value) {
        await api.post(`/groups/${clientFormGroupId.value}/clients/${clientId}`)
      } else if (initialClientGroupId.value) {
        await api.delete(`/groups/${initialClientGroupId.value}/clients/${clientId}`)
      }
      initialClientGroupId.value = clientFormGroupId.value
    } catch (gErr) {
      const gMsg = errMessage(gErr)
      formError.value = clientFieldsChanged
        ? `Client details saved, but group assignment failed: ${gMsg}`
        : `Group assignment failed: ${gMsg}`
      flash('Group update failed')
      await Promise.all([load(), loadGroups()])
      saving.value = false
      return
    }
  }

  if (clientFieldsChanged && groupChanged) {
    flash('Client details and group assignment saved')
  } else if (groupChanged) {
    flash('Group assignment saved')
  } else {
    flash(editingId.value ? 'Client updated' : 'Client added')
  }
  showForm.value = false
  saving.value = false
  await Promise.all([load(), loadGroups()])
}

// ---------- row actions ----------
async function toggleActive(c) {
  if (!isHigh.value) return
  try {
    await api.patch(`/clients/${c.id}`, toBody({ ...fromClient(c), is_active: !c.is_active }))
    c.is_active = !c.is_active
    flash(c.is_active ? 'Client marked active' : 'Client marked inactive')
  } catch (e) {
    fail(e)
  }
}

async function remove(c) {
  if (!isHigh.value) return
  if (!confirm(`Delete ${c.business_name}? This cannot be undone.`)) return
  try {
    await api.delete(`/clients/${c.id}`)
    flash('Client deleted')
    await load()
  } catch (e) {
    fail(e)
  }
}

// ---------- MEDIUM user client-group management drawer ----------
const showManageGroupDrawer = ref(false)
const clientForGroupMgmt = ref(null)
const manageGroupError = ref('')
const manageGroupSaving = ref(false)
const manageGroupSearch = ref('')
const newGroupNameInMgmt = ref('')

const filteredGroupsForMgmt = computed(() => {
  const q = manageGroupSearch.value.trim().toLowerCase()
  if (!q) return groups.value || []
  return (groups.value || []).filter((g) => g.name.toLowerCase().includes(q))
})

function openManageGroupDrawer(client) {
  if (!canManageGroups.value) return
  clientForGroupMgmt.value = client
  manageGroupError.value = ''
  manageGroupSearch.value = ''
  newGroupNameInMgmt.value = ''
  showManageGroupDrawer.value = true
  loadGroups()
}

function closeManageGroupDrawer() {
  showManageGroupDrawer.value = false
  clientForGroupMgmt.value = null
  manageGroupError.value = ''
}

async function assignGroupToClient(targetGroupId) {
  if (!clientForGroupMgmt.value || !canManageGroups.value) return
  const targetGroup = (groups.value || []).find((g) => g.id === targetGroupId)
  if (!targetGroup) return

  const currentGroupId = clientForGroupMgmt.value.group_id
  if (currentGroupId === targetGroupId) return

  if (currentGroupId) {
    const curName = getGroupName(currentGroupId) || 'another group'
    const proceed = window.confirm(
      `${clientForGroupMgmt.value.business_name} currently belongs to "${curName}". Are you sure you want to move them to "${targetGroup.name}"?`
    )
    if (!proceed) return
  }

  manageGroupSaving.value = true
  manageGroupError.value = ''
  try {
    await api.post(`/groups/${targetGroupId}/clients/${clientForGroupMgmt.value.id}`)
    flash(`Assigned ${clientForGroupMgmt.value.business_name} to ${targetGroup.name}`)
    await Promise.all([load(), loadGroups()])
    const updated = clients.value.find((c) => c.id === clientForGroupMgmt.value.id)
    if (updated) clientForGroupMgmt.value = updated
  } catch (e) {
    manageGroupError.value = errMessage(e)
  } finally {
    manageGroupSaving.value = false
  }
}

async function removeGroupMembershipForClient() {
  if (!clientForGroupMgmt.value || !clientForGroupMgmt.value.group_id || !canManageGroups.value) return
  const curGroupId = clientForGroupMgmt.value.group_id
  const curGroupName = getGroupName(curGroupId) || 'this group'
  const proceed = window.confirm(
    `Remove ${clientForGroupMgmt.value.business_name} from "${curGroupName}"? The client will become ungrouped.`
  )
  if (!proceed) return

  manageGroupSaving.value = true
  manageGroupError.value = ''
  try {
    await api.delete(`/groups/${curGroupId}/clients/${clientForGroupMgmt.value.id}`)
    flash(`Removed ${clientForGroupMgmt.value.business_name} from group`)
    await Promise.all([load(), loadGroups()])
    const updated = clients.value.find((c) => c.id === clientForGroupMgmt.value.id)
    if (updated) clientForGroupMgmt.value = updated
  } catch (e) {
    manageGroupError.value = errMessage(e)
  } finally {
    manageGroupSaving.value = false
  }
}

async function createAndAssignGroupInMgmt() {
  if (!clientForGroupMgmt.value || !canManageGroups.value) return
  const trimmed = newGroupNameInMgmt.value.trim()
  if (!trimmed) {
    manageGroupError.value = 'Group name is required.'
    return
  }
  if (trimmed.length > 100) {
    manageGroupError.value = 'Group name cannot exceed 100 characters.'
    return
  }

  manageGroupSaving.value = true
  manageGroupError.value = ''
  let newGroup = null
  try {
    const res = await api.post('/groups/', { name: trimmed })
    newGroup = res.data
    await loadGroups()
  } catch (e) {
    manageGroupError.value = errMessage(e)
    manageGroupSaving.value = false
    return
  }

  try {
    await api.post(`/groups/${newGroup.id}/clients/${clientForGroupMgmt.value.id}`)
    flash(`Created "${newGroup.name}" and assigned ${clientForGroupMgmt.value.business_name}`)
    newGroupNameInMgmt.value = ''
    await Promise.all([load(), loadGroups()])
    const updated = clients.value.find((c) => c.id === clientForGroupMgmt.value.id)
    if (updated) clientForGroupMgmt.value = updated
  } catch (e) {
    manageGroupError.value = `Group created, but client assignment failed: ${errMessage(e)}`
    newGroupNameInMgmt.value = ''
    await Promise.all([load(), loadGroups()])
  } finally {
    manageGroupSaving.value = false
  }
}

// ---------- family groups drawer ----------
const showGroupDrawer = ref(false)
const groupSearchQuery = ref('')
const selectedGroupId = ref(null)
const selectedGroupMembers = ref([])
const loadingMembers = ref(false)
const memberSearchQuery = ref('')
const groupDrawerError = ref('')
const newGroupName = ref('')
const creatingGroup = ref(false)
const renameValue = ref('')
const renamingGroup = ref(false)
const deletingGroup = ref(false)

// Searchable client picker state in Family Groups drawer
const addClientQuery = ref('')
const selectedClientToAdd = ref(null)
const assigningClient = ref(false)
const unlinkingClientId = ref(null)

const selectedGroup = computed(() => (groups.value || []).find((g) => g.id === selectedGroupId.value) || null)

// Filtered groups by search query
const filteredGroups = computed(() => {
  const q = groupSearchQuery.value.trim().toLowerCase()
  if (!q) return groups.value || []
  return (groups.value || []).filter((g) => g.name.toLowerCase().includes(q))
})

// Filtered members in selected group
const filteredSelectedGroupMembers = computed(() => {
  const q = memberSearchQuery.value.trim().toLowerCase()
  if (!q) return selectedGroupMembers.value || []
  return (selectedGroupMembers.value || []).filter((m) => {
    return [m.business_name, m.alias_name, m.gst_details, m.pan_details, m.contact_name]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
  })
})

// Candidates to add (excluding clients already in this group)
const availableCandidatesToAdd = computed(() => {
  if (!selectedGroup.value) return []
  return (clients.value || []).filter((c) => c.group_id !== selectedGroup.value.id)
})

const matchingClientsToAdd = computed(() => {
  const q = addClientQuery.value.trim().toLowerCase()
  if (!q) return availableCandidatesToAdd.value.slice(0, 20)
  return availableCandidatesToAdd.value.filter((c) => {
    return [c.business_name, c.alias_name, c.gst_details, c.pan_details, c.contact_name]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
  }).slice(0, 20)
})

const totalMatchingClientsToAdd = computed(() => {
  const q = addClientQuery.value.trim().toLowerCase()
  if (!q) return availableCandidatesToAdd.value.length
  return availableCandidatesToAdd.value.filter((c) => {
    return [c.business_name, c.alias_name, c.gst_details, c.pan_details, c.contact_name]
      .some((v) => String(v ?? '').toLowerCase().includes(q))
  }).length
})

const addClientMovingWarning = computed(() => {
  if (!selectedClientToAdd.value || !selectedGroup.value) return ''
  const c = selectedClientToAdd.value
  if (c.group_id && c.group_id !== selectedGroup.value.id) {
    const oldGroupName = getGroupName(c.group_id) || 'another group'
    const name = c.business_name || 'This client'
    return `${name} currently belongs to "${oldGroupName}". Adding this client will move them to "${selectedGroup.value.name}".`
  }
  return ''
})

// Reactive security watcher: close unauthorized drawers if permissions change during context switch
watch([isHigh, canManageGroups], ([high, canManage]) => {
  if (!high && showForm.value) {
    showForm.value = false
  }
  if (!canManage && showManageGroupDrawer.value) {
    showManageGroupDrawer.value = false
  }
})

async function openGroupDrawer() {
  groupDrawerError.value = ''
  newGroupName.value = ''
  groupSearchQuery.value = ''
  memberSearchQuery.value = ''
  addClientQuery.value = ''
  selectedClientToAdd.value = null
  showGroupDrawer.value = true
  await loadGroups()
  if (selectedGroupId.value) {
    await loadGroupDetails(selectedGroupId.value)
  }
}

function closeGroupDrawer() {
  showGroupDrawer.value = false
  groupDrawerError.value = ''
  selectedClientToAdd.value = null
  addClientQuery.value = ''
}

async function selectGroup(id) {
  selectedGroupId.value = id
  selectedClientToAdd.value = null
  addClientQuery.value = ''
  memberSearchQuery.value = ''
  groupDrawerError.value = ''
  await loadGroupDetails(id)
}

async function loadGroupDetails(id) {
  if (!id) {
    selectedGroupMembers.value = []
    renameValue.value = ''
    return
  }
  loadingMembers.value = true
  groupDrawerError.value = ''
  try {
    const res = await api.get(`/groups/${id}`)
    selectedGroupMembers.value = res.data.clients || []
    renameValue.value = res.data.name || ''
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    loadingMembers.value = false
  }
}

async function createGroup() {
  const trimmed = newGroupName.value.trim()
  if (!trimmed) {
    groupDrawerError.value = 'Group name is required.'
    return
  }
  if (trimmed.length > 100) {
    groupDrawerError.value = 'Group name cannot exceed 100 characters.'
    return
  }
  creatingGroup.value = true
  groupDrawerError.value = ''
  try {
    const res = await api.post('/groups/', { name: trimmed })
    newGroupName.value = ''
    flash(`Group "${res.data.name}" created`)
    await loadGroups()
    await selectGroup(res.data.id)
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    creatingGroup.value = false
  }
}

async function renameGroup() {
  if (!selectedGroup.value || !canManageGroups.value) return
  const trimmed = renameValue.value.trim()
  if (!trimmed) {
    groupDrawerError.value = 'Group name is required.'
    return
  }
  if (trimmed.length > 100) {
    groupDrawerError.value = 'Group name cannot exceed 100 characters.'
    return
  }
  if (trimmed === selectedGroup.value.name) return

  renamingGroup.value = true
  groupDrawerError.value = ''
  try {
    const res = await api.patch(`/groups/${selectedGroup.value.id}`, { name: trimmed })
    flash(`Group renamed to "${res.data.name}"`)
    await Promise.all([loadGroups(), load(), loadGroupDetails(selectedGroup.value.id)])
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    renamingGroup.value = false
  }
}

async function confirmDeleteGroup() {
  if (!selectedGroup.value || !canManageGroups.value) return
  const g = selectedGroup.value
  const msg = `Are you sure you want to delete the group "${g.name}"?\n\nDeleting this group will not delete its clients. The clients will become ungrouped.`
  if (!window.confirm(msg)) return

  deletingGroup.value = true
  groupDrawerError.value = ''
  try {
    await api.delete(`/groups/${g.id}`)
    flash(`Group "${g.name}" deleted`)
    if (groupFilter.value === String(g.id)) {
      groupFilter.value = ''
    }
    selectedGroupId.value = null
    selectedGroupMembers.value = []
    await Promise.all([loadGroups(), load()])
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    deletingGroup.value = false
  }
}

async function assignSelectedClient() {
  if (!selectedGroup.value || !selectedClientToAdd.value || !canManageGroups.value) return
  assigningClient.value = true
  groupDrawerError.value = ''
  try {
    await api.post(`/groups/${selectedGroup.value.id}/clients/${selectedClientToAdd.value.id}`)
    flash(`Added ${selectedClientToAdd.value.business_name} to ${selectedGroup.value.name}`)
    selectedClientToAdd.value = null
    addClientQuery.value = ''
    await Promise.all([
      loadGroupDetails(selectedGroup.value.id),
      loadGroups(),
      load()
    ])
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    assigningClient.value = false
  }
}

async function removeMember(client) {
  if (!selectedGroup.value || !canManageGroups.value) return
  unlinkingClientId.value = client.id
  groupDrawerError.value = ''
  try {
    await api.delete(`/groups/${selectedGroup.value.id}/clients/${client.id}`)
    flash(`Removed ${client.business_name} from group`)
    await Promise.all([
      loadGroupDetails(selectedGroup.value.id),
      loadGroups(),
      load()
    ])
  } catch (e) {
    groupDrawerError.value = errMessage(e)
  } finally {
    unlinkingClientId.value = null
  }
}
</script>

<template>
  <section>
    <PageHeader title="Clients" :subtitle="subtitle">
      <button type="button" class="btn" @click="openGroupDrawer">Family Groups</button>
      <button v-if="canAddClient" class="btn primary" @click="openForm()">Add client</button>
    </PageHeader>

    <div class="filters">
      <input v-model="search" type="search" placeholder="Search name, alias, matter, GST or PAN" aria-label="Search clients" />
      <select v-model="activeFilter" @change="load" aria-label="Status filter">
        <option value="all">All clients</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <select v-model="categoryFilter" aria-label="Category filter">
        <option value="">All categories</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-model="groupFilter" aria-label="Family group filter">
        <option value="">All groups</option>
        <option value="ungrouped">Ungrouped</option>
        <option v-for="g in groups" :key="g.id" :value="String(g.id)">{{ g.name }}</option>
      </select>
    </div>

    <AlertMessages :error="error" :toast="toast" />
    <p v-if="taskWarning" class="banner error" role="alert">{{ taskWarning }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Business</th><th>Contact</th><th>Categories</th><th>Handled by</th><th>Status</th>
            <th v-if="canViewClientActions" class="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td :colspan="canViewClientActions ? 6 : 5" class="empty">Loading clients…</td></tr>
          <tr v-else-if="!visible.length">
            <td :colspan="canViewClientActions ? 6 : 5" class="empty">
              No clients match. Clear the filters<span v-if="canAddClient"> or <a href="#" @click.prevent="openForm()">add a client</a></span>.
            </td>
          </tr>
          <tr v-for="c in visible" :key="c.id">
            <td>
              <strong>{{ c.business_name }}</strong>
              <span v-if="c.alias_name" class="chip alias-chip">Alias: {{ c.alias_name }}</span>
              <span v-if="getGroupName(c.group_id)" class="chip group-chip">Group: {{ getGroupName(c.group_id) }}</span>
              <span v-if="matchingMatterBadge(c.id)" class="chip matter-chip">Matter: {{ matchingMatterBadge(c.id) }}</span>
              <div class="small">
                <span v-if="c.gst_details">GST {{ c.gst_details }}</span>
                <span v-if="c.pan_details"> PAN {{ c.pan_details }}</span>
              </div>
            </td>
            <td>{{ c.contact_name || '—' }}<div class="small">{{ c.mobile_number }}</div></td>
            <td>
              <span v-for="cat in c.categories || []" :key="cat.id" class="chip">{{ cat.name }}</span>
              <span v-if="!c.categories?.length" class="small">—</span>
            </td>
            <td>{{ staffName(c.assigned_staff_id) }}</td>
            <td>
              <button v-if="isHigh" class="pill" :class="c.is_active ? 'on' : 'off'" @click="toggleActive(c)"
                :title="c.is_active ? 'Click to mark inactive' : 'Click to mark active'">
                {{ c.is_active ? 'Active' : 'Inactive' }}
              </button>
              <span v-else class="pill" :class="c.is_active ? 'on' : 'off'" style="cursor: default">
                {{ c.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td v-if="canViewClientActions" class="right">
              <button v-if="isHigh" class="btn" @click="openForm(c)">Edit</button>
              <button v-if="isHigh" class="btn danger" @click="remove(c)">Delete</button>
              <button v-if="isMedium" class="btn" @click="openManageGroupDrawer(c)">Manage Group</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Client Add / Edit Drawer (HIGH full edit) -->
    <FormDrawer v-if="showForm" :title="editingId ? 'Edit client' : 'Add client'" :error="formError"
      :saving="saving" :submit-label="editingId ? 'Save changes' : 'Add client'"
      @close="showForm = false" @submit="save">
      <div class="two">
        <label>Business name *<input v-model="form.business_name" required maxlength="150" /></label>
        <label>Alias name (optional)<input v-model="form.alias_name" maxlength="150" placeholder="e.g. Gupta Traders" /></label>
      </div>
      <div class="two">
        <label v-for="[key, label] in TEXT_FIELDS" :key="key">{{ label }}<input v-model="form[key]" /></label>
      </div>
      <div class="two">
        <label>Primary category
          <select v-model="form.category_id">
            <option value="">None</option>
            <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <label>Assigned staff
          <select v-model="form.assigned_staff_id">
            <option value="">Unassigned</option>
            <option v-for="s in staff" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
      </div>
      <fieldset>
        <legend>All applicable categories</legend>
        <label v-for="c in categories" :key="c.id" class="check">
          <input type="checkbox" :value="c.id" v-model="form.category_ids" /> {{ c.name }}
        </label>
      </fieldset>
      <label class="check"><input type="checkbox" v-model="form.is_active" /> Client is active</label>

      <!-- Family Group Section inside Edit Client -->
      <div v-if="editingId" class="edit-group-section">
        <div class="edit-group-header">
          <label class="section-label">Family Group</label>
          <button
            v-if="!showCreateGroupInEdit"
            type="button"
            class="mini"
            @click="showCreateGroupInEdit = true"
          >
            + New Group
          </button>
        </div>

        <!-- Inline New Group Creator -->
        <div v-if="showCreateGroupInEdit" class="inline-create-group">
          <input
            v-model="newGroupNameInEdit"
            maxlength="100"
            placeholder="New group name..."
            :disabled="creatingGroupInEdit"
            @keydown.enter.prevent="createGroupInEdit"
          />
          <button
            type="button"
            class="btn primary mini"
            :disabled="creatingGroupInEdit || !newGroupNameInEdit.trim()"
            @click="createGroupInEdit"
          >
            {{ creatingGroupInEdit ? 'Creating…' : 'Create & Select' }}
          </button>
          <button
            type="button"
            class="btn mini"
            @click="showCreateGroupInEdit = false; newGroupNameInEdit = ''"
          >
            Cancel
          </button>
        </div>

        <div class="current-group-status">
          <span class="small muted-text">Current group:</span>
          <strong>{{ getGroupName(clientFormGroupId) || 'None (Ungrouped)' }}</strong>
          <button
            v-if="clientFormGroupId"
            type="button"
            class="mini danger"
            @click="clientFormGroupId = null"
            title="Remove from group"
          >
            Remove from Group
          </button>
        </div>

        <!-- Searchable group picker for Edit Client -->
        <div class="group-picker-box">
          <input
            v-model="editGroupSearch"
            type="search"
            placeholder="Search family groups..."
            aria-label="Search family groups"
          />
          <div class="group-picker-options">
            <div
              class="group-picker-option"
              :class="{ active: clientFormGroupId === null }"
              @click="clientFormGroupId = null"
            >
              <span>No group (Ungrouped)</span>
            </div>
            <div
              v-for="g in filteredGroupsForEdit"
              :key="g.id"
              class="group-picker-option"
              :class="{ active: clientFormGroupId === g.id }"
              @click="clientFormGroupId = g.id"
            >
              <span>{{ g.name }}</span>
              <span class="small muted-text">({{ g.client_count }} {{ g.client_count === 1 ? 'client' : 'clients' }})</span>
            </div>
            <p v-if="!filteredGroupsForEdit.length && editGroupSearch.trim()" class="small muted-text empty-picker">
              No groups match "{{ editGroupSearch }}"
            </p>
          </div>
        </div>

        <p v-if="groupChangeWarning" class="warning-note">
          {{ groupChangeWarning }}
        </p>
      </div>
    </FormDrawer>

    <!-- MEDIUM User Manage Group Drawer (permission-safe, no ordinary client fields) -->
    <div v-if="showManageGroupDrawer" class="overlay" @click.self="closeManageGroupDrawer" @keydown.esc="closeManageGroupDrawer">
      <div class="drawer manage-group-drawer" role="dialog" aria-modal="true" :aria-label="'Manage Group for ' + (clientForGroupMgmt?.business_name || 'Client')">
        <div class="drawer-header">
          <div>
            <h2>Manage Family Group</h2>
            <div class="small muted-text">
              Client: <strong>{{ clientForGroupMgmt?.business_name }}</strong>
              <span v-if="clientForGroupMgmt?.alias_name" class="chip alias-chip">Alias: {{ clientForGroupMgmt?.alias_name }}</span>
            </div>
          </div>
          <button type="button" class="mini" @click="closeManageGroupDrawer" aria-label="Close drawer">✕</button>
        </div>

        <p v-if="manageGroupError" class="banner error" role="alert">{{ manageGroupError }}</p>

        <div class="current-group-status">
          <span class="small muted-text">Current group:</span>
          <strong>{{ getGroupName(clientForGroupMgmt?.group_id) || 'None (Ungrouped)' }}</strong>
          <button
            v-if="clientForGroupMgmt?.group_id && canManageGroups"
            type="button"
            class="mini danger"
            :disabled="manageGroupSaving"
            @click="removeGroupMembershipForClient"
          >
            {{ manageGroupSaving ? 'Removing…' : 'Remove from Group' }}
          </button>
        </div>

        <!-- Create & Assign New Group (MEDIUM/HIGH) -->
        <div v-if="canManageGroups" class="create-group-box">
          <label for="mgmt-new-group-name">Create & assign new group</label>
          <div class="group-input-row">
            <input
              id="mgmt-new-group-name"
              v-model="newGroupNameInMgmt"
              maxlength="100"
              placeholder="New group name..."
              :disabled="manageGroupSaving"
              @keydown.enter.prevent="createAndAssignGroupInMgmt"
            />
            <button
              type="button"
              class="btn primary"
              :disabled="manageGroupSaving || !newGroupNameInMgmt.trim()"
              @click="createAndAssignGroupInMgmt"
            >
              {{ manageGroupSaving ? 'Creating…' : 'Create & Assign' }}
            </button>
          </div>
        </div>

        <!-- Assign / Move to Existing Group -->
        <div v-if="canManageGroups" class="assign-existing-box">
          <label class="section-label">Assign to existing group</label>
          <input
            v-model="manageGroupSearch"
            type="search"
            placeholder="Search family groups..."
            aria-label="Search family groups"
          />
          <div class="group-picker-options">
            <div
              v-for="g in filteredGroupsForMgmt"
              :key="g.id"
              class="group-picker-option"
              :class="{ active: clientForGroupMgmt?.group_id === g.id }"
              @click="assignGroupToClient(g.id)"
            >
              <div class="picker-option-main">
                <strong>{{ g.name }}</strong>
                <span class="small muted-text">({{ g.client_count }} {{ g.client_count === 1 ? 'client' : 'clients' }})</span>
              </div>
              <span v-if="clientForGroupMgmt?.group_id === g.id" class="chip">Current</span>
              <button
                v-else
                type="button"
                class="mini primary"
                :disabled="manageGroupSaving"
              >
                {{ clientForGroupMgmt?.group_id ? 'Move here' : 'Assign' }}
              </button>
            </div>
            <p v-if="!filteredGroupsForMgmt.length && manageGroupSearch.trim()" class="small muted-text empty-picker">
              No groups match "{{ manageGroupSearch }}"
            </p>
            <p v-else-if="!groups.length" class="small muted-text empty-picker">
              No family groups exist yet. Create one above.
            </p>
          </div>
        </div>

        <div class="actions">
          <button type="button" class="btn" @click="closeManageGroupDrawer">Close</button>
        </div>
      </div>
    </div>

    <!-- Family Groups Drawer (General Group Management & Explorer) -->
    <div v-if="showGroupDrawer" class="overlay" @click.self="closeGroupDrawer" @keydown.esc="closeGroupDrawer">
      <div class="drawer group-drawer" role="dialog" aria-modal="true" aria-label="Family Groups">
        <div class="drawer-header">
          <h2>Family Groups</h2>
          <button type="button" class="mini" @click="closeGroupDrawer" aria-label="Close drawer">✕</button>
        </div>

        <p v-if="groupDrawerError" class="banner error" role="alert">{{ groupDrawerError }}</p>

        <!-- Create Group (HIGH and MEDIUM only) -->
        <div v-if="canManageGroups" class="create-group-box">
          <label for="new-group-name">Create new family group</label>
          <div class="group-input-row">
            <input
              id="new-group-name"
              v-model="newGroupName"
              maxlength="100"
              placeholder="e.g. Sharma Family"
              :disabled="creatingGroup"
              @keydown.enter.prevent="createGroup"
            />
            <button
              type="button"
              class="btn primary"
              :disabled="creatingGroup || !newGroupName.trim()"
              @click="createGroup"
            >
              {{ creatingGroup ? 'Creating…' : 'Create' }}
            </button>
          </div>
        </div>

        <!-- Groups Section with Search -->
        <div class="groups-section">
          <h3 class="section-title">All Groups</h3>
          <input
            v-model="groupSearchQuery"
            type="search"
            placeholder="Search family groups..."
            aria-label="Search family groups"
          />
          <p v-if="groupsLoading" class="small muted-text">Loading groups…</p>
          <p v-else-if="!groups.length" class="small muted-text">No family groups created yet.</p>
          <p v-else-if="!filteredGroups.length" class="small muted-text">No family groups match your search.</p>
          <div v-else class="groups-list">
            <div
              v-for="g in filteredGroups"
              :key="g.id"
              class="group-card"
              :class="{ selected: selectedGroupId === g.id }"
              @click="selectGroup(g.id)"
            >
              <div class="group-card-header">
                <span class="group-name">{{ g.name }}</span>
                <span class="chip">{{ g.client_count }} {{ g.client_count === 1 ? 'client' : 'clients' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Selected Group Detail Section -->
        <div v-if="selectedGroup" class="selected-group-section">
          <div class="selected-group-header">
            <div>
              <h3 class="section-title">{{ selectedGroup.name }}</h3>
              <div class="small muted-text">{{ selectedGroupMembers.length }} {{ selectedGroupMembers.length === 1 ? 'member' : 'members' }}</div>
            </div>
          </div>

          <!-- Rename & Delete (HIGH and MEDIUM only) -->
          <div v-if="canManageGroups" class="group-mgmt-box">
            <div class="rename-row">
              <input
                v-model="renameValue"
                maxlength="100"
                placeholder="Rename group"
                :disabled="renamingGroup"
                @keydown.enter.prevent="renameGroup"
              />
              <button
                type="button"
                class="btn"
                :disabled="renamingGroup || !renameValue.trim() || renameValue.trim() === selectedGroup.name"
                @click="renameGroup"
              >
                {{ renamingGroup ? 'Saving…' : 'Rename' }}
              </button>
            </div>
            <div class="delete-row">
              <button
                type="button"
                class="btn danger"
                :disabled="deletingGroup"
                @click="confirmDeleteGroup"
              >
                {{ deletingGroup ? 'Deleting…' : 'Delete Group' }}
              </button>
            </div>
          </div>

          <!-- Member List with Search -->
          <div class="members-box">
            <h4 class="subsection-title">Member Clients</h4>
            <input
              v-model="memberSearchQuery"
              type="search"
              placeholder="Search group members..."
              aria-label="Search group members"
            />
            <p v-if="loadingMembers" class="small muted-text">Loading members…</p>
            <p v-else-if="!selectedGroupMembers.length" class="small muted-text">No clients in this group yet.</p>
            <p v-else-if="!filteredSelectedGroupMembers.length" class="small muted-text">No members match your search.</p>
            <ul v-else class="member-list">
              <li v-for="m in filteredSelectedGroupMembers" :key="m.id" class="member-item">
                <div class="member-info">
                  <strong>{{ m.business_name }}</strong>
                  <span v-if="m.alias_name" class="chip alias-chip">Alias: {{ m.alias_name }}</span>
                </div>
                <button
                  v-if="canManageGroups"
                  type="button"
                  class="mini danger"
                  :disabled="unlinkingClientId === m.id"
                  @click="removeMember(m)"
                  title="Remove from group"
                >
                  {{ unlinkingClientId === m.id ? '…' : 'Remove' }}
                </button>
              </li>
            </ul>
          </div>

          <!-- Add Member to Group: Searchable Client Picker (HIGH and MEDIUM only) -->
          <div v-if="canManageGroups" class="add-member-box">
            <label class="section-label">Add client to this group</label>
            <input
              v-model="addClientQuery"
              type="search"
              placeholder="Search clients by name, alias, GST, PAN..."
              aria-label="Search clients to add"
            />

            <!-- Selected client preview -->
            <div v-if="selectedClientToAdd" class="selected-client-preview">
              <div class="client-preview-info">
                <strong>{{ selectedClientToAdd.business_name }}</strong>
                <span v-if="selectedClientToAdd.alias_name" class="chip alias-chip">Alias: {{ selectedClientToAdd.alias_name }}</span>
                <span v-if="selectedClientToAdd.group_id" class="chip group-chip">In: {{ getGroupName(selectedClientToAdd.group_id) }}</span>
              </div>
              <button type="button" class="mini" @click="selectedClientToAdd = null" aria-label="Clear selection">✕ Clear</button>
            </div>

            <!-- Client results list -->
            <div v-else class="client-results-box">
              <p v-if="!availableCandidatesToAdd.length" class="small muted-text">All clients are already in this group.</p>
              <p v-else-if="!matchingClientsToAdd.length" class="small muted-text">No matching clients found.</p>
              <div v-else class="client-results-list">
                <div
                  v-for="c in matchingClientsToAdd"
                  :key="c.id"
                  class="client-result-item"
                  @click="selectedClientToAdd = c"
                >
                  <div class="client-result-main">
                    <strong>{{ c.business_name }}</strong>
                    <span v-if="c.alias_name" class="chip alias-chip">Alias: {{ c.alias_name }}</span>
                    <span v-if="c.group_id" class="chip group-chip">In: {{ getGroupName(c.group_id) }}</span>
                  </div>
                  <div class="small muted-text">
                    <span v-if="c.contact_name">{{ c.contact_name }}</span>
                    <span v-if="c.gst_details"> · GST: {{ c.gst_details }}</span>
                    <span v-if="c.pan_details"> · PAN: {{ c.pan_details }}</span>
                  </div>
                </div>
                <p v-if="totalMatchingClientsToAdd > 20" class="small muted-text results-more">
                  Showing top 20 of {{ totalMatchingClientsToAdd }} matches. Type to refine.
                </p>
              </div>
            </div>

            <p v-if="addClientMovingWarning" class="warning-note">
              {{ addClientMovingWarning }}
            </p>

            <div class="picker-actions">
              <button
                type="button"
                class="btn primary"
                :disabled="!selectedClientToAdd || assigningClient"
                @click="assignSelectedClient"
              >
                {{ assigningClient ? 'Adding…' : 'Add to Group' }}
              </button>
            </div>
          </div>
        </div>

        <div class="actions">
          <button type="button" class="btn" @click="closeGroupDrawer">Close</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.alias-chip {
  margin-left: 0.4rem;
  font-size: 0.78rem;
  font-weight: 500;
  vertical-align: middle;
  background: var(--sunken);
  color: var(--muted);
  border: 1px solid var(--line);
}

.group-chip {
  margin-left: 0.4rem;
  font-size: 0.78rem;
  font-weight: 500;
  vertical-align: middle;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid var(--line);
}

.matter-chip {
  margin-left: 0.4rem;
  font-size: 0.78rem;
  font-weight: 500;
  vertical-align: middle;
  background: var(--warn-soft);
  color: var(--warn);
  border: 1px solid var(--line);
}

.group-drawer,
.manage-group-drawer {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.75rem;
}

.drawer-header h2 {
  margin: 0;
}

.section-label {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--muted);
}

.section-title {
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--ink);
}

.subsection-title {
  font-size: 0.88rem;
  font-weight: 600;
  margin: 0 0 0.4rem 0;
  color: var(--muted);
}

.muted-text {
  color: var(--muted);
  margin: 0.25rem 0;
}

/* Create Group Box */
.create-group-box {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.8rem;
  background: var(--sunken);
  border: 1px solid var(--line);
  border-radius: 6px;
}

.create-group-box label {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--muted);
}

.group-input-row {
  display: flex;
  gap: 0.5rem;
}

.group-input-row input {
  flex: 1;
}

/* Groups Section */
.groups-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.4rem;
  background: var(--surface);
}

.group-card {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.group-card:hover {
  border-color: var(--accent);
}

.group-card.selected {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.group-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-name {
  font-weight: 600;
  font-size: 0.92rem;
}

/* Selected Group Section */
.selected-group-section {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 0.9rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.selected-group-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.5rem;
}

.group-mgmt-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.rename-row {
  display: flex;
  gap: 0.5rem;
}

.rename-row input {
  flex: 1;
}

.delete-row {
  display: flex;
  justify-content: flex-end;
}

/* Member List */
.members-box {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.2rem;
}

.member-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 160px;
  overflow-y: auto;
}

.member-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 5px;
}

.member-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
}

/* Searchable Client Picker in Family Groups Drawer */
.add-member-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--line);
}

.client-results-box {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.4rem;
  background: var(--surface);
}

.client-results-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-height: 180px;
  overflow-y: auto;
}

.client-result-item {
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--paper);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.client-result-item:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.client-result-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.results-more {
  text-align: center;
  margin: 0.3rem 0;
  font-style: italic;
}

.selected-client-preview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.7rem;
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 6px;
}

.client-preview-info {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.picker-actions {
  display: flex;
  justify-content: flex-end;
}

.warning-note {
  margin: 0.2rem 0 0 0;
  font-size: 0.82rem;
  color: var(--warn);
  line-height: 1.3;
}

/* Family Group Section in Edit Client */
.edit-group-section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.8rem;
  background: var(--sunken);
  border: 1px solid var(--line);
  border-radius: 6px;
  margin-top: 0.4rem;
}

.edit-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.current-group-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.4rem 0.6rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 5px;
}

.inline-create-group {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  padding: 0.5rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
}

.inline-create-group input {
  flex: 1;
}

.group-picker-box {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.group-picker-options {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.35rem;
  background: var(--surface);
}

.group-picker-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: var(--paper);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.group-picker-option:hover {
  border-color: var(--accent);
}

.group-picker-option.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  font-weight: 600;
}

.empty-picker {
  text-align: center;
  padding: 0.5rem;
}

/* MEDIUM User Manage Group Drawer */
.assign-existing-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.picker-option-main {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
</style>
