<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'
import BaseButton from '../base/BaseButton.vue'

withDefaults(defineProps<{
  title: string
  subtitle?: string
  showBack?: boolean
  backText?: string
}>(), {
  subtitle: '',
  showBack: false,
  backText: '返回',
})

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__main">
      <BaseButton
        v-if="showBack"
        variant="ghost"
        size="sm"
        class="page-header__back"
        @click="emit('back')"
      >
        <ChevronLeft :size="16" />
        {{ backText }}
      </BaseButton>

      <div class="page-header__heading">
        <h1 class="page-header__title">{{ title }}</h1>
        <p v-if="subtitle" class="page-header__subtitle">
          {{ subtitle }}
        </p>
      </div>
    </div>

    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>

  <div v-if="$slots.extra" class="page-header__extra">
    <slot name="extra" />
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.page-header__main {
  display: flex;
  align-items: center;
  min-width: 0;
  flex: 1;
}

.page-header__back {
  flex-shrink: 0;
  margin-right: 8px;
}

.page-header__heading {
  display: flex;
  align-items: baseline;
  min-width: 0;
  gap: 16px;
}

.page-header__title {
  flex-shrink: 0;
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-xl, 28px);
  font-weight: 700;
  line-height: 1.3;
  white-space: nowrap;
}

.page-header__subtitle {
  min-width: 0;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base, 14px);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page-header__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 10px;
}

.page-header__extra {
  margin-bottom: 20px;
}

/* Responsive */
@media (max-width: 1024px) {
  .page-header__subtitle {
    white-space: normal;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .page-header__main {
    flex-wrap: wrap;
  }

  .page-header__heading {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .page-header__subtitle {
    white-space: normal;
  }

  .page-header__actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
