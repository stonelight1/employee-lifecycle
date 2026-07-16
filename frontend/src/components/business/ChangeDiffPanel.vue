<script setup lang="ts">
interface DiffItem {
  label: string
  before?: string
  after?: string
  changed: boolean
}

defineProps<{
  items?: DiffItem[]
}>()
</script>

<template>
  <div class="diff-panel">
    <div class="diff-header">
      <span class="diff-col diff-before">变更前</span>
      <span class="diff-arrow" />
      <span class="diff-col diff-after">变更后</span>
    </div>
    <div v-for="(item, idx) in items" :key="idx" class="diff-row" :class="{ changed: item.changed }">
      <div class="diff-label">{{ item.label }}</div>
      <div class="diff-values">
        <span class="diff-col diff-before">{{ item.before || '—' }}</span>
        <span class="diff-arrow">→</span>
        <span class="diff-col diff-after">{{ item.after || '—' }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diff-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.diff-header {
  display: grid;
  grid-template-columns: 1fr 24px 1fr;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-bg);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  font-weight: 500;
}
.diff-row {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
.diff-row.changed {
  background: var(--color-primary-soft);
}
.diff-label {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  padding-top: 2px;
}
.diff-values {
  display: grid;
  grid-template-columns: 1fr 24px 1fr;
  gap: 8px;
  align-items: center;
}
.diff-before {
  color: var(--color-text-secondary);
}
.diff-after {
  color: var(--color-text-primary);
  font-weight: 500;
}
.diff-row.changed .diff-after {
  color: var(--color-primary);
}
.diff-arrow {
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}
</style>
