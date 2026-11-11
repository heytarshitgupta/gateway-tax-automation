<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import { useNotify, errMessage } from '../composables/useApi'
import PageHeader from '../layouts/PageHeader.vue'
import AlertMessages from '../layouts/AlertMessages.vue'

const { authenticatedUser, updateProfile } = useCurrentStaff()
const { error, toast, flash, fail } = useNotify()

const form = reactive({
  name: '',
  mobile_number: '',
})

const saving = ref(false)

function syncForm() {
  if (authenticatedUser.value) {
    form.name = authenticatedUser.value.name || ''
    form.mobile_number = authenticatedUser.value.mobile_number || ''
  }
}

onMounted(() => {
  syncForm()
})

watch(
  () => authenticatedUser.value,
  () => {
    syncForm()
  },
  { deep: true }
)

async function handleSave() {
  const trimmedName = form.name.trim()
  if (!trimmedName) {
    fail({ message: 'Name cannot be blank or whitespace-only.' })
    return
  }
  if (trimmedName.length > 100) {
    fail({ message: 'Name must be 100 characters or fewer.' })
    return
  }

  const trimmedMobile = form.mobile_number.trim()
  if (trimmedMobile.length > 20) {
    fail({ message: 'Mobile number must be 20 characters or fewer.' })
    return
  }

  saving.value = true
  try {
    await updateProfile({
      name: trimmedName,
      mobile_number: trimmedMobile || null,
    })
    flash('Profile updated successfully')
  } catch (err) {
    fail(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section>
    <PageHeader title="My Profile" subtitle="View and manage your personal staff profile" />

    <AlertMessages :error="error" :toast="toast" />

    <div class="panel">
      <form @submit.prevent="handleSave" class="profile-form">
        <div class="two">
          <label>
            Full Name *
            <input
              v-model="form.name"
              type="text"
              required
              maxlength="100"
              placeholder="e.g. Rahul Sharma"
              :disabled="saving"
            />
          </label>
          <label>
            Mobile Number
            <input
              v-model="form.mobile_number"
              type="tel"
              inputmode="tel"
              maxlength="20"
              placeholder="e.g. +91 98765 43210"
              :disabled="saving"
            />
          </label>
        </div>

        <div class="two">
          <label>
            Email Address (Login ID)
            <input
              :value="authenticatedUser?.email || '—'"
              type="email"
              disabled
              readonly
              class="readonly-input"
            />
          </label>
          <label>
            Professional Designation
            <input
              :value="authenticatedUser?.role || '—'"
              type="text"
              disabled
              readonly
              class="readonly-input"
            />
          </label>
        </div>

        <div class="two">
          <label>
            System Access Level
            <div class="meta-field">
              <span class="chip">{{ authenticatedUser?.access_level || 'LOW' }}</span>
            </div>
          </label>
          <label>
            Account Status
            <div class="meta-field">
              <span
                class="pill"
                :class="authenticatedUser?.is_active ? 'on' : 'off'"
                style="cursor: default"
              >
                {{ authenticatedUser?.is_active ? 'Active' : 'Inactive' }}
              </span>
            </div>
          </label>
        </div>

        <div class="actions">
          <button type="submit" class="btn primary" :disabled="saving">
            {{ saving ? 'Saving changes…' : 'Save changes' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<style scoped>
.profile-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.profile-form label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--muted);
}
.readonly-input {
  background: var(--sunken);
  color: var(--muted);
  cursor: not-allowed;
  opacity: 0.85;
}
.meta-field {
  padding: 0.45rem 0;
  display: flex;
  align-items: center;
}
</style>

