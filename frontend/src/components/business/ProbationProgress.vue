<script setup lang="ts">
import { computed } from 'vue'
import { calculateProbationProgress, formatDate, calculateOverdueText } from '@/utils/date'

const props = withDefaults(defineProps<{
  hireDate?: string | null
  probationEndDate?: string | null
  showLabel?: boolean
  size?: 'sm' | 'md'
}>(), {
  showLabel: true,
  size: 'sm',
})

const progress = computed(() => calculateProbationProgress(props.hireDate, props.probationEndDate))
const overdue = computed(() => calculateOverdueText(props.probationEndDate))
const showProgress = computed(() => !!(props.hireDate && props.probationEndDate))

const barHeight = computed(() => props.size === 'sm' ? 6 : 8)
</script>

<template>
  <div v-if="showProgress" class="probation-progress">
    <div v-if="showLabel" class="progress-header">
      <span class="progress-label">试用期 {{ progress }}%</span>
      <span v-if="overdue" class="progress-overdue">{{ overdue }}</span>
    </div>
    <div class="progress-bar" :style="{ height: barHeight + 'px' }">
      <div
        class="progress-fill"
        :class="{ overdue: !!overdue }"
        :style="{ width: progress + '%' }"
      />
    </div>
    <div v-if="showLabel && probationEndDate" class="progress-end">
      <span class="text-xs text-tertiary">预计 {{ formatDate(probationEndDate) }} 转正</span>
    </div>
  </div>
  <span v-else class="text-tertiary text-xs">—</span>
</template>

<style scoped>
.probation-progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.progress-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.progress-overdue {
  font-size: var(--font-size-xs);
  color: var(--color-danger);
  font-weight: 500;
}
.progress-bar {
  background: var(--color-bg);
  border-radius: 99px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 99px;
  transition: width 0.3s ease;
}
.progress-fill.overdue {
  background: var(--color-warning);
}
.progress-end {
  display: flex;
  justify-content: flex-end;
}
</style>
