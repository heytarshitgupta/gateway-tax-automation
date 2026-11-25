<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import api from '../api'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const props = defineProps({
  initialAddMode: {
    type: Boolean,
    default: false,
  },
  inline: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close', 'matter-updated'])

const { isHigh } = useCurrentStaff()

const matters = ref([])
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')

// Add matter state
const showAddForm = ref(props.initialAddMode)
const newMatterName = ref('')
const adding = ref(false)
const addError = ref('')

// Delete matter confirmation state
const deletingId = ref(null)
const deletingName = ref('')
const deleting = ref(false)

const filteredMatters = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return matters.value
  return matters.value.filter((m) => m.name && m.name.toLowerCase().includes(q))
})

async function fetchMatters() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/matter-types/')
    matters.value = Array.isArray(data) ? data : []
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load matter catalogue.'
  } finally {
    loading.value = false
  }
}

async function handleAddMatter() {
  const trimmed = newMatterName.value.trim().replace(/\s+/g, ' ')
  if (!trimmed) {
    addError.value = 'Matter name is required and cannot be whitespace only.'
    return
  }
  if (trimmed.length > 200) {
    addError.value = 'Matter name cannot exceed 200 characters.'
    return
  }

  adding.value = true
  addError.value = ''
  try {
    await api.post('/matter-types/', { name: trimmed })
    newMatterName.value = ''
    showAddForm.value = false
    await fetchMatters()
    emit('matter-updated')
  } catch (err) {
    if (err.response?.status === 409) {
      addError.value = 'A matter with this name already exists in the catalogue.'
    } else {
      addError.value = err.response?.data?.detail || err.message || 'Failed to create matter.'
    }
  } finally {
    adding.value = false
  }
}

function promptDelete(matter) {
  deletingId.value = matter.id
  deletingName.value = matter.name
}

function cancelDelete() {
  deletingId.value = null
  deletingName.value = ''
}

async function confirmDelete() {
  if (!deletingId.value) return
  deleting.value = true
  try {
    await api.delete(`/matter-types/${deletingId.value}`)
    deletingId.value = null
    deletingName.value = ''
    await fetchMatters()
    emit('matter-updated')
  } catch (err) {
    if (err.response?.status === 404) {
      // Already deleted
      deletingId.value = null
      deletingName.value = ''
      await fetchMatters()
      emit('matter-updated')
    } else {
      alert(err.response?.data?.detail || 'Failed to delete matter.')
    }
  } finally {
    deleting.value = false
  }
}

watch(
  () => props.initialAddMode,
  (val) => {
    if (val && isHigh.value) {
      showAddForm.value = true
      newMatterName.value = ''
      addError.value = ''
    }
  }
)

watch(isHigh, (high) => {
  if (!high) {
    showAddForm.value = false
    deletingId.value = null
    deletingName.value = ''
    addError.value = ''
  }
})

onMounted(() => {
  fetchMatters()
})
</script>

<template>
  <div :class="inline ? 'matters-inline-host' : 'overlay'" @click.self="!inline && $emit('close')" @keydown.esc="!inline && $emit('close')">
    <div
      :class="inline ? 'matter-inline-panel matter-drawer matters-drawer' : 'drawer matter-drawer matters-drawer'"
      :role="inline ? 'region' : 'dialog'"
      :aria-modal="inline ? undefined : 'true'"
      aria-label="Matter Catalogue"
    >
      <div class="drawer-header">
        <div>
          <h2 v-if="!inline">Matter Catalogue</h2>
          <p class="sub">
            Available matters: <strong>{{ matters.length }}</strong>
          </p>
        </div>
        <button v-if="!inline" type="button" class="btn mini" aria-label="Close drawer" @click="$emit('close')">
          &times;
        </button>
      </div>

      <p v-if="error" class="banner error" role="alert">{{ error }}</p>

      <!-- Search bar and Add trigger -->
      <div class="catalogue-actions">
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search matters…"
          class="matter-search matters-search-input"
          aria-label="Search matters"
        />
        <button
          v-if="isHigh && !showAddForm"
          type="button"
          class="btn primary"
          @click="showAddForm = true; newMatterName = ''; addError = ''"
        >
          + Add Matter
        </button>
      </div>

      <!-- Inline Add Matter Form for HIGH users -->
      <form v-if="showAddForm && isHigh" class="add-matter-box" @submit.prevent="handleAddMatter">
        <h3>Add New Matter</h3>
        <label>
          Matter name *
          <input
            v-model="newMatterName"
            type="text"
            maxlength="200"
            placeholder="e.g. GST Audit Consultation"
            :disabled="adding"
            required
            autocomplete="off"
            aria-label="New matter name"
          />
        </label>
        <p v-if="addError" class="banner error small-banner" role="alert">{{ addError }}</p>
        <div class="add-form-actions">
          <button type="button" class="btn mini" :disabled="adding" @click="showAddForm = false">
            Cancel
          </button>
          <button type="submit" class="btn mini primary" :disabled="adding">
            {{ adding ? 'Saving…' : 'Save Matter' }}
          </button>
        </div>
      </form>

      <!-- Delete Confirmation Banner -->
      <div v-if="deletingId && isHigh" class="delete-confirm-box confirm-row" role="alertdialog" aria-labelledby="del-title">
        <p id="del-title" class="del-msg">
          Delete "<strong>{{ deletingName }}</strong>" from the available matter list?
          <br />
          <span class="small">Existing tasks using this matter will not be affected.</span>
        </p>
        <div class="del-actions">
          <button type="button" class="btn mini" :disabled="deleting" @click="cancelDelete">
            Cancel
          </button>
          <button type="button" class="btn mini danger del-confirm-btn" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? 'Deleting…' : 'Confirm Delete' }}
          </button>
        </div>
      </div>

      <!-- Matters List -->
      <div class="matters-list-wrap">
        <div v-if="loading" class="empty">Loading matter catalogue…</div>
        <div v-else-if="matters.length === 0" class="empty">
          No matter types in catalogue.<br />
          <span v-if="isHigh">Click "+ Add Matter" above to create one.</span>
        </div>
        <div v-else-if="filteredMatters.length === 0" class="empty">
          No matters matching "{{ searchQuery }}".
        </div>
        <div v-else class="matters-chips" role="list">
          <div v-for="m in filteredMatters" :key="m.id" class="matter-chip matter-item matter-row" role="listitem">
            <span class="matter-name m-name">{{ m.name }}</span>
            <button
              v-if="isHigh"
              type="button"
              class="chip-del-btn delete-btn del-btn"
              title="Delete matter"
              :aria-label="`Delete ${m.name}`"
              @click="promptDelete(m)"
            >
              &times;
            </button>
          </div>
        </div>
      </div>

      <div v-if="!inline" class="actions">
        <button type="button" class="btn" @click="$emit('close')">Close</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.matters-inline-host {
  width: 100%;
}

.matter-inline-panel {
  display: flex;
  flex-direction: column;
}

.matter-drawer {
  display: flex;
  flex-direction: column;
}

.drawer.matter-drawer {
  width: min(540px, 100%);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.catalogue-actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 0.8rem;
}

.matter-search {
  flex: 1;
}

.add-matter-box {
  background: var(--sunken);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.8rem;
  margin-bottom: 0.8rem;
}

.add-matter-box h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.small-banner {
  margin: 0.4rem 0;
  padding: 0.35rem 0.6rem;
  font-size: 0.85rem;
}

.add-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.delete-confirm-box {
  background: var(--danger-soft);
  border: 1px solid var(--danger);
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 0.8rem;
}

.del-msg {
  margin: 0 0 0.5rem;
  color: var(--danger);
}

.del-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.matters-list-wrap {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  min-height: 120px;
}

.matters-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  padding: 0.85rem;
  align-items: flex-start;
  align-content: flex-start;
}

.matter-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--sunken);
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.3;
  max-width: 100%;
}

.matter-name {
  white-space: normal;
  word-break: break-word;
}

.chip-del-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 1.05rem;
  line-height: 1;
  padding: 0 0.15rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-del-btn:hover {
  color: var(--danger);
}
</style>
