<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
  actionLabel?: string
}>(), {
  title: '暂无数据',
  description: '',
  actionLabel: '',
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="empty-state">
    <svg class="empty-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
    <h4 class="empty-title">{{ title }}</h4>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <button v-if="actionLabel" class="empty-action" @click="emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  color: var(--color-text-tertiary);
}
.empty-icon {
  margin-bottom: 12px;
  opacity: 0.4;
}
.empty-title {
  font-size: var(--font-size-base);
  font-weight: 500;
  margin-bottom: 4px;
}
.empty-desc {
  font-size: var(--font-size-sm);
  margin-bottom: 12px;
}
.empty-action {
  padding: 6px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-primary);
  cursor: pointer;
  font-size: var(--font-size-sm);
}
.empty-action:hover {
  background: var(--color-primary-soft);
}
</style>
