<script setup>
import { useRoute } from 'vue-router'
import PageHeader from '../layouts/PageHeader.vue'

const route = useRoute()
</script>

<template>
  <PageHeader :title="route.meta.title" subtitle="This page isn't built yet." />
</template>