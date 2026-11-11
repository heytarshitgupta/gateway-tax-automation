<script setup>
defineProps({ error: String, toast: String })
</script>

<template>
  <p v-if="error" class="banner error" role="alert">{{ error }}</p>
  <p v-if="toast" class="banner ok" role="status">{{ toast }}</p>
</template>