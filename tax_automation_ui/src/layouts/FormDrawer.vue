<script setup>
defineProps({
  title: String,
  error: String,
  saving: Boolean,
  submitLabel: { type: String, default: 'Save' },
})
defineEmits(['close', 'submit'])
</script>

<template>
  <div class="overlay" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <form class="drawer" role="dialog" aria-modal="true" :aria-label="title" @submit.prevent="$emit('submit')">
      <h2>{{ title }}</h2>
      <slot />
      <p v-if="error" class="banner error" role="alert">{{ error }}</p>
      <div class="actions">
        <button type="button" class="btn" @click="$emit('close')">Cancel</button>
        <button type="submit" class="btn primary" :disabled="saving">{{ saving ? 'Saving…' : submitLabel }}</button>
      </div>
    </form>
  </div>
</template>