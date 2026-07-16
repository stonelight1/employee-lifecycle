<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
  actionLabel?: string
  actionType?: 'primary' | 'secondary'
  overdue?: number
  loading?: boolean
}>(), {
  title: '暂无需处理事项',
  description: '当前员工所有事项均已处理',
  actionLabel: '',
  actionType: 'primary',
  overdue: 0,
  loading: false,
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="next-action" :class="{ 'has-overdue': overdue > 0 }">
    <div class="action-content">
      <div class="action-title">
        <span v-if="overdue > 0" class="overdue-badge">{{ overdue }} 天逾期</span>
        <span>{{ title }}</span>
      </div>
      <p v-if="description" class="action-desc">{{ description }}</p>
    </div>
    <button
      v-if="actionLabel"
      class="action-btn"
      :class="actionType"
      :disabled="loading"
      @click="emit('action')"
    >
      <span v-if="loading" class="spinner" />
      {{ actionLabel }}
    </button>
  </div>
</template>

<style scoped>
.next-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--color-primary-soft);
  gap: 16px;
}
.next-action.has-overdue {
  background: var(--color-danger-soft);
}
.action-content {
  flex: 1;
  min-width: 0;
}
.action-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}
.overdue-badge {
  font-size: var(--font-size-xs);
  background: var(--color-danger);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
}
.action-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.action-btn {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.action-btn.primary {
  background: var(--color-primary);
  color: #fff;
}
.action-btn.primary:hover {
  background: var(--color-primary-hover);
}
.action-btn.secondary {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
