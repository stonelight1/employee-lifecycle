<script setup lang="ts">
import { computed } from 'vue'
import { lifecycleStageInfo } from '@/utils/lifecycle'
import { getStatusLabel, employeeStatusMap } from '@/constants/status'
import BaseBadge from '@/components/base/BaseBadge.vue'

const props = withDefaults(defineProps<{
  status?: string
  size?: 'sm' | 'md'
}>(), {
  size: 'sm',
})

const stageInfo = computed(() => {
  if (!props.status) return null
  return lifecycleStageInfo[props.status] || null
})
</script>

<template>
  <BaseBadge
    v-if="stageInfo"
    :label="stageInfo.label"
    :color="stageInfo.color"
    :background="stageInfo.background"
    :size="size"
  />
  <BaseBadge v-else :label="getStatusLabel(employeeStatusMap, status)" :size="size" />
</template>
