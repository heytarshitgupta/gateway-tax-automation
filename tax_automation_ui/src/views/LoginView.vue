<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCurrentStaff } from '../composables/useCurrentStaff'
import { errMessage } from '../composables/useApi'

const router = useRouter()
const { login } = useCurrentStaff()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!email.value.trim() || !password.value) {
    error.value = 'Email and password are required.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await login(email.value.trim(), password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = errMessage(e) || 'Invalid email or password.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="brand-header">
        <div class="logo">GS</div>
        <div>
          <div class="brand-name">Gateway Solutions</div>
          <div class="brand-tag">Tax Office Automation</div>
        </div>
      </div>

      <div v-if="error" class="banner error" role="alert">
        {{ error }}
      </div>

      <form @submit.prevent="handleLogin">
        <label>
          Email *
          <input
            v-model="email"
            type="email"
            required
            autocomplete="username"
            placeholder="e.g. staff@gatewaytax.in"
            autofocus
          />
        </label>

        <label class="pwd-field">
          Password *
          <input
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            placeholder="Enter your password"
          />
        </label>

        <button type="submit" class="btn primary submit-btn" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--paper);
  padding: 1.5rem;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 2.25rem 2rem;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-bottom: 1.75rem;
  justify-content: center;
}

.brand-name {
  color: var(--ink);
  font-weight: 700;
  font-size: 1.1rem;
}

.brand-tag {
  color: var(--muted);
  font-size: 0.8rem;
}

.pwd-field {
  margin-top: 1rem;
  display: block;
}

.submit-btn {
  width: 100%;
  margin-top: 1.5rem;
  padding: 0.65rem 1rem;
  font-size: 0.95rem;
  font-weight: 600;
}
</style>

