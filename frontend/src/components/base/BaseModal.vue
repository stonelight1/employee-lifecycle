<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  show?: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  loading?: boolean
  closeOnMask?: boolean
}>(), {
  show: false,
  title: '确认操作',
  message: '',
  confirmText: '确认',
  cancelText: '取消',
  danger: false,
  loading: false,
  closeOnMask: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function onMaskClick() {
  if (props.closeOnMask) emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay" @click.self="onMaskClick">
        <div class="modal-card" role="dialog" aria-modal="true" :aria-label="title">
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
          </div>
          <div class="modal-body">
            <slot name="message">
              <p>{{ message }}</p>
            </slot>
          </div>
          <div class="modal-footer">
            <button class="modal-btn modal-btn-cancel" @click="emit('cancel')">
              {{ cancelText }}
            </button>
            <button
              class="modal-btn"
              :class="danger ? 'modal-btn-danger' : 'modal-btn-confirm'"
              :disabled="loading"
              @click="emit('confirm')"
            >
              <span v-if="loading" class="btn-spinner" />
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  width: 420px;
  max-width: 90vw;
  box-shadow: var(--shadow-popover);
}
.modal-header {
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border);
}
.modal-title {
  font-size: var(--font-size-md);
  font-weight: 600;
}
.modal-body {
  padding: var(--space-5) var(--space-6);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--color-border);
}
.modal-btn {
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--color-border);
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.modal-btn-cancel {
  background: var(--color-surface);
  color: var(--color-text-primary);
}
.modal-btn-cancel:hover {
  background: var(--color-bg);
}
.modal-btn-confirm {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.modal-btn-confirm:hover {
  background: var(--color-primary-hover);
}
.modal-btn-danger {
  background: var(--color-danger);
  color: #fff;
  border-color: var(--color-danger);
}
.modal-btn-danger:hover {
  background: #BE123C;
}
.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Transition */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-active .modal-card,
.modal-leave-active .modal-card {
  transition: transform 0.2s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal-card,
.modal-leave-to .modal-card {
  transform: scale(0.95);
}
</style>
