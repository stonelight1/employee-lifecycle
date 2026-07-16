<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'warning'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>(), {
  variant: 'secondary',
  size: 'md',
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  click: [e: MouseEvent]
}>()
</script>

<template>
  <button
    class="base-btn"
    :class="[`btn-${variant}`, `btn-${size}`, { 'btn-loading': loading }]"
    :disabled="disabled || loading"
    @click="emit('click', $event)"
  >
    <span v-if="loading" class="btn-spinner" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4" stroke-linecap="round">
          <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite" />
        </circle>
      </svg>
    </span>
    <slot />
  </button>
</template>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: var(--font-size-base);
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
  user-select: none;
}
.base-btn:hover:not(:disabled) {
  background: var(--color-surface-secondary);
  border-color: var(--color-border-strong);
}
.base-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sizes */
.btn-sm { padding: 4px 10px; font-size: var(--font-size-xs); }
.btn-md { padding: 6px 16px; }
.btn-lg { padding: 10px 20px; font-size: var(--font-size-md); }

/* Variants */
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.btn-danger {
  color: var(--color-danger);
  border-color: var(--color-danger-soft);
  background: var(--color-danger-soft);
}
.btn-danger:hover:not(:disabled) {
  background: var(--color-danger);
  color: #fff;
}

.btn-warning {
  background: var(--color-warning);
  color: #fff;
  border-color: var(--color-warning);
}
.btn-warning:hover:not(:disabled) {
  background: #B45309;
  border-color: #B45309;
}

.btn-ghost {
  border-color: transparent;
  background: transparent;
}
.btn-ghost:hover:not(:disabled) {
  background: var(--color-bg);
}

/* Loading */
.btn-loading {
  position: relative;
}
.btn-spinner {
  display: inline-flex;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
