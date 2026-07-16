<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, removeToast } = useToast()

const iconMap: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: 'i',
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-container" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="`toast-${toast.type}`"
        >
          <span class="toast-icon">{{ iconMap[toast.type] || 'i' }}</span>
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" aria-label="关闭" @click="removeToast(toast.id)">✕</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
}
.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  box-shadow: var(--shadow-popover);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  animation: toast-in 0.3s ease;
}
.toast-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.toast-message {
  flex: 1;
  color: var(--color-text-primary);
}
.toast-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-tertiary);
  font-size: 12px;
  padding: 2px;
}
.toast-close:hover {
  color: var(--color-text-primary);
}

.toast-success .toast-icon {
  background: var(--color-success-soft);
  color: var(--color-success);
}
.toast-error .toast-icon {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.toast-warning .toast-icon {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}
.toast-info .toast-icon {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
