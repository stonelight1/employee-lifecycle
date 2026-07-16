<script setup lang="ts">
import { computed } from 'vue'
import { riskMap } from '@/constants/status'
import BaseBadge from '@/components/base/BaseBadge.vue'

const props = withDefaults(defineProps<{
  level?: string
  size?: 'sm' | 'md'
}>(), {
  size: 'sm',
})

const riskInfo = computed(() => {
  if (!props.level) return null
  return riskMap[props.level] || null
})
</script>

<template>
  <BaseBadge
    v-if="riskInfo"
    :label="riskInfo.label"
    :color="riskInfo.color"
    :background="riskInfo.background"
    :size="size"
  />
  <span v-else-if="!level" class="text-tertiary text-xs">—</span>
</template>
