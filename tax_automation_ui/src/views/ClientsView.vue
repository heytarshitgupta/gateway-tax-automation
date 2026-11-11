<script setup>
import { ref, reactive, computed } from 'vue'
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

// ---------- data ----------
const { error, toast, flash, fail } = useNotify()
const { isHigh, isMedium } = useCurrentStaff()
const canAddClient = computed(() => isHigh.value || isMedium.value)

const search = ref('')
const activeFilter = ref('all') // all | active | inactive
const categoryFilter = ref('')

const { items: clients, loading, load } = useList('/clients', fail, () =>
  activeFilter.value === 'all' ? {} : { is_active: activeFilter.value === 'active' }
)
const { items: categories } = useList('/categories', fail)
const { items: staff } = useList('/staff', fail)

const staffName = (id) => staff.value.find((s) => s.id === id)?.name || '—'

const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  const cat = Number(categoryFilter.value)
  return clients.value.filter((c) => {
    if (cat && c.category_id !== cat && !(c.categories || []).some((x) => x.id === cat)) return false
    return !q || [c.business_name, c.alias_name, ...TEXT_FIELDS.map(([k]) => c[k])].some((v) => String(v ?? '').toLowerCase().includes(q))
  })
})
const subtitle = computed(() => `${visible.value.length} of ${clients.value.length} shown`)

// ---------- form ----------
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

function openForm(client = null) {
  if (client && !isHigh.value) return
  if (!client && !canAddClient.value) return
  editingId.value = client?.id ?? null
  Object.assign(form, client ? fromClient(client) : blankForm())
  formError.value = ''
  showForm.value = true
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
  try {
    if (editingId.value) await api.patch(`/clients/${editingId.value}`, toBody(form))
    else await api.post('/clients', toBody(form))
    flash(editingId.value ? 'Client updated' : 'Client added')
    showForm.value = false
    await load()
  } catch (e) {
    formError.value = errMessage(e)
  } finally {
    saving.value = false
  }
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
    fail(e) // e.g. client still has tasks or invoices
  }
}
</script>

<template>
  <section>
    <PageHeader title="Clients" :subtitle="subtitle">
      <button v-if="canAddClient" class="btn primary" @click="openForm()">Add client</button>
    </PageHeader>

    <div class="filters">
      <input v-model="search" type="search" placeholder="Search name, mobile, GST or PAN" aria-label="Search clients" />
      <select v-model="activeFilter" @change="load" aria-label="Status filter">
        <option value="all">All clients</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <select v-model="categoryFilter" aria-label="Category filter">
        <option value="">All categories</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
    </div>

    <AlertMessages :error="error" :toast="toast" />

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Business</th><th>Contact</th><th>Categories</th><th>Handled by</th><th>Status</th>
            <th v-if="isHigh" class="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td :colspan="isHigh ? 6 : 5" class="empty">Loading clients…</td></tr>
          <tr v-else-if="!visible.length">
            <td :colspan="isHigh ? 6 : 5" class="empty">
              No clients match. Clear the filters<span v-if="canAddClient"> or <a href="#" @click.prevent="openForm()">add a client</a></span>.
            </td>
          </tr>
          <tr v-for="c in visible" :key="c.id">
            <td>
              <strong>{{ c.business_name }}</strong>
              <span v-if="c.alias_name" class="chip alias-chip">Alias: {{ c.alias_name }}</span>
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
            <td v-if="isHigh" class="right">
              <button class="btn" @click="openForm(c)">Edit</button>
              <button class="btn danger" @click="remove(c)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

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
    </FormDrawer>
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
</style>
