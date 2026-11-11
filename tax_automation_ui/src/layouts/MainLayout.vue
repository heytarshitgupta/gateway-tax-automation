<script setup>
import { RouterView } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
</script>

<template>
  <div class="shell">
    <AppSidebar />
    <main class="page"><RouterView /></main>
  </div>
</template>