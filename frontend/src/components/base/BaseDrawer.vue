<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  show?: boolean
  width?: string
}>(), {
  title: '',
  show: false,
  width: '480px',
})

const emit = defineEmits<{
  close: []
}>()

function onMaskClick() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="show" class="drawer-overlay" @click.self="onMaskClick">
        <div class="drawer-panel" :style="{ width }">
          <div class="drawer-header">
            <h3 class="drawer-title">{{ title }}</h3>
            <button class="drawer-close" aria-label="关闭" @click="emit('close')">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="drawer-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}
.drawer-panel {
  background: var(--color-surface);
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-popover);
}
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.drawer-title {
  font-size: var(--font-size-md);
  font-weight: 600;
}
.drawer-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-secondary);
  padding: 4px;
  border-radius: 4px;
}
.drawer-close:hover {
  background: var(--color-bg);
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}

/* Transition */
.drawer-enter-active, .drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active .drawer-panel,
.drawer-leave-active .drawer-panel {
  transition: transform 0.2s ease;
}
.drawer-enter-from, .drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel {
  transform: translateX(100%);
}
</style>
