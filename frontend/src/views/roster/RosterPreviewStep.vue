<script setup lang="ts">
import { ref } from 'vue'
import { ChevronRight, AlertTriangle, AlertCircle } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import { getStatusLabel } from '@/constants/status'
import type { PreviewResponse, RowPreviewItem } from '@/types/roster-import'

const props = defineProps<{
  previewData: PreviewResponse | null
  previewRows: RowPreviewItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  continue: []
  prev: []
}>()

const previewFilter = ref('ALL')

const filterTabs = [
  { label: '全部', value: 'ALL' },
  { label: '新增', value: 'NEW' },
  { label: '更新', value: 'UPDATE' },
  { label: '待确认', value: 'NEEDS_CONFIRMATION' },
  { label: '错误', value: 'ERROR' },
  { label: '无变化', value: 'UNCHANGED' },
  { label: '跳过', value: 'SKIPPED' },
]

const filteredRows = ref<RowPreviewItem[]>([])

// Watch props.previewRows and previewFilter to update filteredRows
import { watch } from 'vue'
watch([() => props.previewRows, previewFilter], () => {
  if (previewFilter.value === 'ALL') {
    filteredRows.value = props.previewRows
  } else {
    filteredRows.value = props.previewRows.filter(r => r.row_status === previewFilter.value)
  }
}, { immediate: true })

const previewSummaryList = [
  { label: '新增员工', key: 'new_count' as const, color: '#16825D', bg: '#EAF8F1' },
  { label: '自动更新', key: 'update_count' as const, color: '#2563EB', bg: '#EFF6FF' },
  { label: '需要确认', key: 'confirmation_count' as const, color: '#D97706', bg: '#FFF7E8' },
  { label: '数据错误', key: 'error_count' as const, color: '#E11D48', bg: '#FFF1F2' },
  { label: '无变化', key: 'unchanged_count' as const, color: '#667085', bg: '#F2F4F7' },
  { label: '跳过', key: 'skipped_count' as const, color: '#98A2B3', bg: '#F2F4F7' },
]

const expandedRowNos = ref<Set<number>>(new Set())

function toggleRowExpand(rowNo: number) {
  const newSet = new Set(expandedRowNos.value)
  if (newSet.has(rowNo)) newSet.delete(rowNo)
  else newSet.add(rowNo)
  expandedRowNos.value = newSet
}

const rowStatusInfo: Record<string, { label: string; color: string; background: string }> = {
  NEW: { label: '新增', color: '#16825D', background: '#EAF8F1' },
  UPDATE: { label: '更新', color: '#2563EB', background: '#EFF6FF' },
  UNCHANGED: { label: '无变化', color: '#667085', background: '#F2F4F7' },
  NEEDS_CONFIRMATION: { label: '待确认', color: '#D97706', background: '#FFF7E8' },
  ERROR: { label: '错误', color: '#E11D48', background: '#FFF1F2' },
  SKIPPED: { label: '跳过', color: '#98A2B3', background: '#F2F4F7' },
  IMPORTED: { label: '已导入', color: '#16825D', background: '#EAF8F1' },
}

const changeTypeLabel: Record<string, string> = {
  NEW: '新增', UPDATE: '更新', UNCHANGED: '无变化',
  CONFIRMATION: '需确认', REMOVAL: '移除',
}
</script>

<template>
  <div class="step-content">
    <div class="card step-card">
      <h2 class="step-title">数据预览</h2>
      <p class="step-desc">预览本次导入将执行的操作。</p>

      <!-- Summary cards -->
      <div v-if="previewData" class="summary-cards">
        <div
          v-for="item in previewSummaryList"
          :key="item.key"
          class="summary-card"
          :style="{ borderTopColor: item.color }"
        >
          <div class="summary-count" :style="{ color: item.color }">
            {{ previewData!.summary[item.key] }}
          </div>
          <div class="summary-label">{{ item.label }}</div>
        </div>
      </div>

      <!-- Filter tabs -->
      <div class="preview-filters">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          class="filter-tab"
          :class="{ active: previewFilter === tab.value }"
          @click="previewFilter = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Rows table -->
      <table class="preview-table">
        <thead>
          <tr>
            <th class="col-row">#</th>
            <th class="col-name">姓名</th>
            <th class="col-match">匹配员工</th>
            <th class="col-status-h">状态</th>
            <th class="col-changes">变化</th>
            <th class="col-actions-h"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filteredRows.length === 0">
            <td colspan="6" class="empty-cell"><BaseEmpty title="无匹配数据" /></td>
          </tr>
          <template v-for="row in filteredRows" :key="row.row_no">
            <tr class="preview-row" @click="toggleRowExpand(row.row_no)">
              <td class="col-row">{{ row.row_no }}</td>
              <td class="col-name"><span class="row-name">{{ row.normalized_name }}</span></td>
              <td class="col-match">
                <span v-if="row.matched_employee_name" class="matched-name">{{ row.matched_employee_name }}</span>
                <span v-else class="no-match">—</span>
              </td>
              <td>
                <BaseBadge type="custom" :label="rowStatusInfo[row.row_status]?.label || row.row_status"
                  :color="rowStatusInfo[row.row_status]?.color || '#98A2B3'"
                  :background="rowStatusInfo[row.row_status]?.background || '#F2F4F7'" size="sm" />
              </td>
              <td class="col-changes">
                <span v-if="row.diff_fields && row.diff_fields.length > 0" class="change-count">
                  {{ row.diff_fields.length }} 项变化
                </span>
                <span v-else class="text-tertiary">—</span>
              </td>
              <td>
                <ChevronRight :size="14" class="expand-icon" :class="{ expanded: expandedRowNos.has(row.row_no) }" />
              </td>
            </tr>
            <tr v-if="expandedRowNos.has(row.row_no)" class="diff-row">
              <td colspan="6">
                <div class="diff-detail">
                  <table v-if="row.diff_fields && row.diff_fields.length > 0" class="diff-table">
                    <thead><tr><th>字段</th><th>当前值</th><th>新值</th><th>处理方式</th></tr></thead>
                    <tbody>
                      <tr v-for="(diff, di) in row.diff_fields" :key="di">
                        <td>{{ diff.field_label || diff.field_key }}</td>
                        <td class="diff-old">{{ diff.old_value ?? '—' }}</td>
                        <td class="diff-new">{{ diff.new_value ?? '—' }}</td>
                        <td>
                          <BaseBadge type="custom"
                            :label="getStatusLabel(changeTypeLabel, diff.change_type || 'UPDATE')"
                            :color="diff.change_type === 'NEEDS_CONFIRMATION' ? '#D97706' : '#2563EB'"
                            :background="diff.change_type === 'NEEDS_CONFIRMATION' ? '#FFF7E8' : '#EFF6FF'" size="sm" />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-if="row.issues && row.issues.length > 0" class="row-issues">
                    <div v-for="issue in row.issues" :key="issue.id || issue.issue_code" class="issue-item">
                      <AlertTriangle v-if="issue.severity === 'WARNING'" :size="14" class="issue-warn" />
                      <AlertCircle v-else :size="14" class="issue-error" />
                      <span>{{ issue.title }}</span>
                    </div>
                  </div>
                  <div v-if="(!row.diff_fields || row.diff_fields.length === 0) && (!row.issues || row.issues.length === 0)">
                    <span class="text-tertiary">无数据变化</span>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="form-actions">
        <BaseButton variant="ghost" @click="emit('prev')">上一步</BaseButton>
        <BaseButton variant="primary" @click="emit('continue')">继续 <ChevronRight :size="16" /></BaseButton>
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
.summary-cards { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.summary-card { flex: 1; min-width: 100px; padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); border-top: 3px solid; text-align: center; background: var(--color-surface); }
.summary-count { font-size: var(--font-size-xl); font-weight: 700; line-height: 1.2; }
.summary-label { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-top: 4px; }
.preview-filters { display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; }
.filter-tab { padding: 5px 14px; border: 1px solid var(--color-border); border-radius: 99px; background: var(--color-surface); font-size: var(--font-size-sm); cursor: pointer; }
.filter-tab:hover { border-color: var(--color-primary); color: var(--color-primary); }
.filter-tab.active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.preview-table { width: 100%; border-collapse: collapse; }
.preview-table th, .preview-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.preview-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.preview-row { cursor: pointer; }
.preview-row:hover { background: var(--color-bg); }
.col-row { width: 40px; color: var(--color-text-tertiary); }
.col-name { font-weight: 500; }
.no-match { color: var(--color-text-tertiary); }
.change-count { color: var(--color-primary); font-size: var(--font-size-xs); }
.expand-icon { transition: transform 0.15s; color: var(--color-text-tertiary); }
.expand-icon.expanded { transform: rotate(90deg); }
.empty-cell { text-align: center; }
.diff-row td { padding: 0; background: var(--color-bg); }
.diff-detail { padding: 12px 20px; }
.diff-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.diff-table th, .diff-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-xs); }
.diff-table th { background: var(--color-surface); font-weight: 600; color: var(--color-text-secondary); }
.diff-old { color: var(--color-text-tertiary); }
.diff-new { color: var(--color-primary); font-weight: 500; }
.row-issues { display: flex; flex-direction: column; gap: 4px; }
.issue-item { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.issue-warn { color: var(--color-warning); flex-shrink: 0; }
.issue-error { color: var(--color-danger); flex-shrink: 0; }
.text-tertiary { color: var(--color-text-tertiary); }
</style>
