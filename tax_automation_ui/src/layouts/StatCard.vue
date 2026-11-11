<script setup>
defineProps({ label: String, value: [Number, String], icon: String, tone: { type: String, default: 'blue' } })
</script>

<template>
  <div class="stat">
    <span class="badge" :class="tone" aria-hidden="true">{{ icon }}</span>
    <div>
      <div class="num">{{ value }}</div>
      <div class="lbl">{{ label }}</div>
    </div>
  </div>
</template>