<script setup lang="ts">
interface LifecycleStep {
  key: string
  label: string
  completed: boolean
  current: boolean
}

withDefaults(defineProps<{
  steps?: LifecycleStep[]
}>(), {
  steps: () => [
    { key: 'PENDING', label: '待入职', completed: false, current: false },
    { key: 'PROBATION', label: '试用期', completed: false, current: false },
    { key: 'REGULARIZATION_PENDING', label: '待转正', completed: false, current: false },
    { key: 'ACTIVE', label: '正式在职', completed: false, current: false },
    { key: 'SEPARATED', label: '离职', completed: false, current: false },
  ],
})
</script>

<template>
  <div class="lifecycle-stepper">
    <div
      v-for="(step, index) in steps"
      :key="step.key"
      class="step-item"
      :class="{
        'step-completed': step.completed,
        'step-current': step.current,
        'step-future': !step.completed && !step.current,
      }"
    >
      <div class="step-indicator">
        <div class="step-dot">
          <svg v-if="step.completed" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <div v-if="index < steps.length - 1" class="step-line" />
      </div>
      <span class="step-label">{{ step.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.lifecycle-stepper {
  display: flex;
  align-items: flex-start;
  gap: 0;
}
.step-item {
  display: flex;
  align-items: center;
  flex: 1;
}
.step-indicator {
  display: flex;
  align-items: center;
  flex: 1;
}
.step-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s;
}
.step-completed .step-dot {
  background: var(--color-primary);
  color: #fff;
}
.step-current .step-dot {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 0 0 4px var(--color-primary-soft);
}
.step-future .step-dot {
  background: var(--color-bg);
  border: 2px solid var(--color-border);
}
.step-line {
  flex: 1;
  height: 2px;
  background: var(--color-border);
  margin: 0 4px;
}
.step-completed .step-line {
  background: var(--color-primary);
}
.step-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 4px;
  white-space: nowrap;
  display: none;
}
.step-completed .step-label,
.step-current .step-label {
  display: block;
  color: var(--color-text-primary);
  font-weight: 500;
}
.step-current .step-label {
  color: var(--color-primary);
}
</style>
