<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '../layouts/PageHeader.vue'
import MattersDrawer from '../components/MattersDrawer.vue'
import { useCurrentStaff } from '../composables/useCurrentStaff'

const route = useRoute()
const { isHigh } = useCurrentStaff()

const initialAddMode = computed(() => isHigh.value && route.query.action === 'add')
</script>

<template>
  <section class="matters-page">
    <PageHeader
      title="Matters"
      subtitle="Manage available tax and compliance matter types for task assignment."
    />
    <MattersDrawer :inline="true" :initial-add-mode="initialAddMode" />
  </section>
</template>
