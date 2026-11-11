<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { errMessage, useNotify, useList } from '../composables/useApi'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import PageHeader from '../layouts/PageHeader.vue'
import AlertMessages from '../layouts/AlertMessages.vue'
import FormDrawer from '../layouts/FormDrawer.vue'

const router = useRouter()
const FIELDS = ['name', 'email', 'mobile_number', 'role']

// ---------- data ----------
const { error, toast, flash, fail } = useNotify()
const { isHigh, loadStaff: refreshGlobalStaff } = useCurrentStaff()

onMounted(() => {
  if (!isHigh.value) {
    router.replace('/dashboard')
  }
})

watch(isHigh, (high) => {
  if (!high) {
    router.replace('/dashboard')
  }
})
const search = ref('')
const activeFilter = ref('all') // all | active | inactive
const roleFilter = ref('')

const { items: staff, loading, load } = useList('/staff', fail, () =>
  activeFilter.value === 'all' ? {} : { is_active: activeFilter.value === 'active' }
)

const roles = computed(() => [...new Set(staff.value.map((s) => s.role).filter(Boolean))].sort())
const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  return staff.value.filter(
    (s) =>
      (!roleFilter.value || s.role === roleFilter.value) &&
      (!q || FIELDS.some((k) => String(s[k] ?? '').toLowerCase().includes(q)))
  )
})

const activeHighCount = computed(
  () => staff.value.filter((s) => s.access_level === 'HIGH' && s.is_active).length
)

// ---------- form ----------
const blankForm = () => ({
  name: '',
  email: '',
  password: '',
  mobile_number: '',
  role: '',
  access_level: 'LOW',
  is_active: true,
})
const fromStaff = (s) => ({
  ...Object.fromEntries(FIELDS.map((k) => [k, s[k] ?? ''])),
  password: '',
  access_level: s.access_level || 'LOW',
  is_active: !!s.is_active,
})
const toBody = (f, isNew = false) => {
  const body = {
    name: f.name.trim(),
    ...Object.fromEntries(FIELDS.slice(1).map((k) => [k, f[k]?.trim() || null])),
    access_level: f.access_level || 'LOW',
    is_active: f.is_active,
  }
  if (isNew) {
    body.password = f.password?.trim() || ''
  }
  return body
}

const form = reactive(blankForm())
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')

function openForm(member = null) {
  if (!isHigh.value) return
  editingId.value = member?.id ?? null
  Object.assign(form, member ? fromStaff(member) : blankForm())
  formError.value = ''
  showForm.value = true
}

async function save() {
  if (!form.name.trim()) return (formError.value = 'Name is required.')
  if (!editingId.value) {
    if (!form.email?.trim()) return (formError.value = 'Email is required for new staff member.')
    if (!form.password?.trim()) return (formError.value = 'Password is required for new staff member.')
  }

  // Last active HIGH member protection
  if (editingId.value) {
    const orig = staff.value.find((s) => s.id === editingId.value)
    if (orig && orig.access_level === 'HIGH' && orig.is_active) {
      if ((form.access_level !== 'HIGH' || !form.is_active) && activeHighCount.value <= 1) {
        formError.value = 'Cannot demote or deactivate the last active HIGH staff member.'
        return
      }
    }
  }

  saving.value = true
  formError.value = ''
  try {
    if (editingId.value) await api.patch(`/staff/${editingId.value}`, toBody(form, false))
    else await api.post('/staff', toBody(form, true))
    flash(editingId.value ? 'Staff member updated' : 'Staff member added')
    showForm.value = false
    Object.assign(form, blankForm())
    await load()
    await refreshGlobalStaff()
  } catch (e) {
    formError.value = errMessage(e)
  } finally {
    saving.value = false
  }
}

// ---------- row actions ----------
async function toggleActive(s) {
  if (!isHigh.value) return
  if (s.access_level === 'HIGH' && s.is_active && activeHighCount.value <= 1) {
    fail({ message: 'Cannot deactivate the last active HIGH staff member.' })
    return
  }
  try {
    await api.patch(`/staff/${s.id}`, toBody({ ...fromStaff(s), is_active: !s.is_active }))
    s.is_active = !s.is_active
    flash(s.is_active ? 'Marked active' : 'Marked inactive')
    await refreshGlobalStaff()
  } catch (e) {
    fail(e)
  }
}

async function remove(s) {
  if (!isHigh.value) return
  if (s.access_level === 'HIGH' && s.is_active && activeHighCount.value <= 1) {
    fail({ message: 'Cannot delete the last active HIGH staff member.' })
    return
  }
  if (!confirm(`Delete ${s.name}? Clients or tasks assigned to them may block this.`)) return
  try {
    await api.delete(`/staff/${s.id}`)
    flash('Staff member deleted')
    await load()
    await refreshGlobalStaff()
  } catch (e) {
    fail(e)
  }
}
</script>

<template>
  <section>
    <PageHeader title="Staff" :subtitle="`${visible.length} of ${staff.length} shown`">
      <button v-if="isHigh" class="btn primary" @click="openForm()">Add staff member</button>
    </PageHeader>

    <div v-if="!isHigh" class="banner">
      Staff directory is read-only. Staff management and access level assignment require HIGH access.
    </div>

    <div class="filters">
      <input v-model="search" type="search" placeholder="Search name, email, mobile or role" aria-label="Search staff" />
      <select v-model="activeFilter" @change="load" aria-label="Status filter">
        <option value="all">All staff</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <select v-model="roleFilter" aria-label="Role filter">
        <option value="">All roles</option>
        <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>

    <AlertMessages :error="error" :toast="toast" />

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Role</th>
            <th>Access</th>
            <th>Contact</th>
            <th>Status</th>
            <th v-if="isHigh" class="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td :colspan="isHigh ? 6 : 5" class="empty">Loading staff…</td></tr>
          <tr v-else-if="!visible.length">
            <td :colspan="isHigh ? 6 : 5" class="empty">
              No staff match. Clear the filters<span v-if="isHigh"> or <a href="#" @click.prevent="openForm()">add a staff member</a></span>.
            </td>
          </tr>
          <tr v-for="s in visible" :key="s.id">
            <td><strong>{{ s.name }}</strong></td>
            <td>{{ s.role || '—' }}</td>
            <td><span class="chip">{{ s.access_level }}</span></td>
            <td>
              <a v-if="s.email" :href="`mailto:${s.email}`">{{ s.email }}</a>
              <span v-else>—</span>
              <div class="small">{{ s.mobile_number }}</div>
            </td>
            <td>
              <button v-if="isHigh" class="pill" :class="s.is_active ? 'on' : 'off'" @click="toggleActive(s)"
                :title="s.is_active ? 'Click to mark inactive' : 'Click to mark active'">
                {{ s.is_active ? 'Active' : 'Inactive' }}
              </button>
              <span v-else class="pill" :class="s.is_active ? 'on' : 'off'" style="cursor: default">
                {{ s.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td v-if="isHigh" class="right">
              <button class="btn" @click="openForm(s)">Edit</button>
              <button class="btn danger" @click="remove(s)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <FormDrawer v-if="showForm" :title="editingId ? 'Edit staff member' : 'Add staff member'" :error="formError"
      :saving="saving" :submit-label="editingId ? 'Save changes' : 'Add staff member'"
      @close="showForm = false; Object.assign(form, blankForm())" @submit="save">
      <label>Name *<input v-model="form.name" required /></label>
      <div class="two">
        <label>Email *<input v-model="form.email" type="email" required /></label>
        <label>Mobile number<input v-model="form.mobile_number" inputmode="tel" /></label>
      </div>
      <label v-if="!editingId">
        Password *
        <input
          v-model="form.password"
          type="password"
          required
          autocomplete="new-password"
          placeholder="Enter initial login password"
        />
      </label>
      <label>Role
        <input v-model="form.role" list="staff-roles" placeholder="e.g. Accountant" />
        <datalist id="staff-roles"><option v-for="r in roles" :key="r" :value="r" /></datalist>
      </label>
      <label>Access Level *
        <select v-model="form.access_level" required>
          <option value="LOW">LOW</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="HIGH">HIGH</option>
        </select>
      </label>
      <label class="check"><input type="checkbox" v-model="form.is_active" /> Staff member is active</label>
    </FormDrawer>
  </section>
</template>
