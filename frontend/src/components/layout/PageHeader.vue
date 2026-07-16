<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'
import BaseBadge from '../base/BaseBadge.vue'
import BaseButton from '../base/BaseButton.vue'

withDefaults(defineProps<{
  title: string
  subtitle?: string
  showBack?: boolean
  badgeText?: string
  badgeVariant?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
}>(), {
  subtitle: '',
  showBack: false,
  badgeText: '',
  badgeVariant: 'neutral',
})

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__main">
      <div class="page-header__title-row">
        <BaseButton
          v-if="showBack"
          variant="ghost"
          size="sm"
          class="page-header__back"
          @click="emit('back')"
        >
          <ChevronLeft :size="20" />
        </BaseButton>
        <h1 class="page-header__title">{{ title }}</h1>
        <BaseBadge
          v-if="badgeText"
          :variant="badgeVariant"
          size="sm"
        >
          {{ badgeText }}
        </BaseBadge>
      </div>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.page-header__main {
  min-width: 0;
  flex: 1;
}

.page-header__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-header__back {
  flex-shrink: 0;
}

.page-header__title {
  margin: 0;
  font-size: var(--font-size-lg, 18px);
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-header__subtitle {
  margin: 4px 0 0 0;
  font-size: var(--font-size-sm, 13px);
  color: var(--color-text-secondary);
}

.page-header__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header__actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
