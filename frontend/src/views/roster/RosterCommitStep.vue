<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import { Check } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import type { PreviewSummary } from '@/types/roster-import'

const props = defineProps<{
  previewData: { summary: PreviewSummary } | null
  loading: boolean
}>()

const emit = defineEmits<{
  confirm: []
  prev: []
}>()

const confirmationItems = [
  { label: '新增员工', key: 'new_count' as const, color: '#16825D' },
  { label: '更新员工', key: 'update_count' as const, color: '#2563EB' },
  { label: '需要确认', key: 'confirmation_count' as const, color: '#D97706' },
  { label: '跳过', key: 'skipped_count' as const, color: '#98A2B3' },
]

function hasItems(): boolean {
  if (!props.previewData) return false
  const s = props.previewData.summary
  return confirmationItems.some(item => s[item.key] > 0)
}
</script>

<template>
  <div class="step-content">
    <div class="card step-card">
      <h2 class="step-title">确认导入</h2>
      <p class="step-desc">
        确认后将写入业务数据。导入产生的部分操作可以通过导入记录撤销；
        已经由 HR 确认的合同、银行卡等业务操作不会随批次撤销。
      </p>

      <div v-if="previewData && hasItems()" class="confirm-grid">
        <div
          v-for="item in confirmationItems"
          :key="item.key"
          class="confirm-item"
          :style="{ borderLeftColor: item.color }"
          v-show="previewData.summary[item.key] > 0"
        >
          <div class="confirm-count" :style="{ color: item.color }">{{ previewData.summary[item.key] }}</div>
          <div class="confirm-label">{{ item.label }}</div>
        </div>
      </div>

      <div class="form-actions">
        <BaseButton variant="ghost" @click="emit('prev')">上一步</BaseButton>
        <BaseButton variant="primary" :loading="loading" @click="emit('confirm')">
          <Check :size="16" /> 确认导入
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.step-card { padding: 28px 32px; }
.step-title { font-size: var(--font-size-md); font-weight: 700; margin-bottom: 4px; }
.step-desc { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin-bottom: 20px; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.confirm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.confirm-item { padding: 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); border-left: 3px solid; background: var(--color-surface); }
.confirm-count { font-size: var(--font-size-xl); font-weight: 700; line-height: 1.2; }
.confirm-label { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin-top: 4px; }
</style>
