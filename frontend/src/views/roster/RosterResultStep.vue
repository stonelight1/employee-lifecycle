<script setup lang="ts">
import { Check, X, Download, Eye } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import type { CommitResponse } from '@/types/roster-import'

const props = defineProps<{
  commitResult: CommitResponse | null
  commitFailed: boolean
  commitErrorMessage: string
  batchId: number | null
  loading: boolean
}>()

const emit = defineEmits<{
  retry: []
  viewDetails: []
  downloadFile: []
  backToList: []
}>()

const summaryItems = [
  { label: '新增员工', key: 'new_count' as const, color: '#16825D' },
  { label: '自动更新', key: 'update_count' as const, color: '#2563EB' },
  { label: '需要确认', key: 'confirmation_count' as const, color: '#D97706' },
  { label: '跳过', key: 'skipped_count' as const, color: '#98A2B3' },
]
</script>

<template>
  <div class="step-content">
    <div class="card step-card" :class="commitFailed ? 'result-failed' : 'result-success'">
      <div class="result-icon-wrap">
        <div v-if="commitFailed" class="result-icon result-icon-failed"><X :size="40" /></div>
        <div v-else class="result-icon result-icon-success"><Check :size="40" /></div>
      </div>

      <h2 class="result-title">{{ commitFailed ? '导入失败' : '导入成功' }}</h2>

      <p v-if="commitFailed" class="result-desc result-desc-failed">
        {{ commitErrorMessage || '系统没有写入业务数据' }}
      </p>
      <p v-else class="result-desc">导入已完成，系统已写入业务数据。</p>

      <!-- Summary -->
      <div v-if="!commitFailed && commitResult?.summary" class="result-summary">
        <div v-for="item in summaryItems" :key="item.key" class="result-summary-item"
          v-show="(commitResult!.summary as any)[item.key] > 0">
          <span class="result-summary-count" :style="{ color: item.color }">{{ (commitResult!.summary as any)[item.key] }}</span>
          <span class="result-summary-label">{{ item.label }}</span>
        </div>
      </div>

      <div class="result-actions">
        <BaseButton variant="ghost" @click="emit('backToList')">返回列表</BaseButton>
        <BaseButton variant="secondary" @click="emit('downloadFile')"><Download :size="16" />下载文件</BaseButton>
        <BaseButton variant="primary" @click="emit('viewDetails')"><Eye :size="16" />查看详情</BaseButton>
      </div>

      <div v-if="commitFailed" class="retry-section">
        <BaseButton variant="danger" :loading="loading" @click="emit('retry')">重试导入</BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.step-card { padding: 28px 32px; }
.result-success, .result-failed { text-align: center; }
.result-icon-wrap { margin-bottom: 16px; }
.result-icon { width: 72px; height: 72px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
.result-icon-success { background: var(--color-success-soft); color: var(--color-success); }
.result-icon-failed { background: var(--color-danger-soft); color: var(--color-danger); }
.result-title { font-size: var(--font-size-lg); font-weight: 700; margin-bottom: 8px; }
.result-desc { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin-bottom: 20px; max-width: 480px; margin-left: auto; margin-right: auto; }
.result-desc-failed { color: var(--color-danger); }
.result-summary { display: flex; justify-content: center; gap: 24px; margin-bottom: 24px; flex-wrap: wrap; }
.result-summary-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.result-summary-count { font-size: var(--font-size-xl); font-weight: 700; }
.result-summary-label { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.result-actions { display: flex; justify-content: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.retry-section { margin-top: 8px; }
</style>
