<script setup lang="ts">
import { computed } from 'vue'
import { lifecycleStageMap, riskMap, followupStatusMap } from '@/constants/status'

const props = withDefaults(defineProps<{
  type?: 'lifecycle' | 'risk' | 'status' | 'custom'
  value?: string
  label?: string
  color?: string
  background?: string
  size?: 'sm' | 'md'
}>(), {
  type: 'custom',
  size: 'sm',
})

const style = computed(() => {
  if (props.type === 'lifecycle' && props.value) {
    const map = lifecycleStageMap[props.value]
    if (map) return { color: map.color, background: map.background }
  }
  if (props.type === 'risk' && props.value) {
    const map = riskMap[props.value]
    if (map) return { color: map.color, background: map.background }
  }
  if (props.type === 'status' && props.value) {
    const map = followupStatusMap[props.value]
    if (map) return { color: 'var(--color-text-secondary)', background: 'var(--color-bg)' }
  }
  if (props.color) return { color: props.color, background: props.background || `${props.color}14` }
  return { color: 'var(--color-text-secondary)', background: 'var(--color-bg)' }
})
</script>

<template>
  <span class="base-badge" :class="`badge-${size}`" :style="style">
    {{ label || value || '—' }}
  </span>
</template>

<style scoped>
.base-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
}
.badge-sm {
  padding: 2px 8px;
  font-size: var(--font-size-xs);
}
.badge-md {
  padding: 4px 10px;
  font-size: var(--font-size-sm);
}
</style>
