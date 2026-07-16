<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FileText,
  Download,
  Eye,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  AlertCircle,
  Check,
  Clock,
  Hash,
  List,
} from 'lucide-vue-next'
import { formatDateTime } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { getStatusLabel } from '@/constants/status'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import {
  getBatchDetail,
  getBatchRows,
  getBatchIssues,
  getRollbackPreview,
  executeRollback,
  getFileDownloadUrl,
  revalidateBatch,
  repairBatch,
  syncConfirmations,
} from '@/services/rosterImportService'
import type { IssueItem, RollbackPreviewResponse, RollbackItem } from '@/types/roster-import'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, loading: confirmLoading, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const batchId = computed(() => Number(route.params.id))
const batchDetail = ref<Record<string, any> | null>(null)
const rows = ref<Record<string, any>[]>([])
const totalRows = ref(0)
const issues = ref<IssueItem[]>([])
const loading = ref(false)
const loadingRows = ref(false)
const loadingIssues = ref(false)
const activeTab = ref<'rows' | 'issues'>('rows')

// Row pagination
const rowPage = ref(1)
const rowPageSize = 50
const rowFilterStatus = ref('')

// Rollback preview
const rollbackPreview = ref<RollbackPreviewResponse | null>(null)
const showRollbackPreview = ref(false)

// Revalidation
const revalidating = ref(false)
const revalidationResult = ref<Record<string, any> | null>(null)
const showRevalidation = ref(false)
const repairing = ref(false)
const repairResult = ref<Record<string, any> | null>(null)

// Sync confirmations
const syncing = ref(false)
const syncResult = ref<Record<string, any> | null>(null)
const showSyncResult = ref(false)
const issueTotal = ref(0)
const issuePendingCount = ref(0)
const issueResolvedCount = ref(0)
const issueIgnoredCount = ref(0)

// Batch status map
const batchStatusMap: Record<string, { label: string; color: string; background: string }> = {
  UPLOADED: { label: '已上传', color: '#7C3AED', background: '#F3E8FF' },
  MAPPING_REQUIRED: { label: '需映射', color: '#D97706', background: '#FFF7E8' },
  PREVIEW_READY: { label: '已预览', color: '#2563EB', background: '#EFF6FF' },
  WAITING_RESOLUTION: { label: '待处理问题', color: '#E11D48', background: '#FFF1F2' },
  READY: { label: '就绪', color: '#16825D', background: '#EAF8F1' },
  IMPORTING: { label: '导入中', color: '#4F46E5', background: '#EEF2FF' },
  SUCCEEDED: { label: '已成功', color: '#16825D', background: '#EAF8F1' },
  FAILED: { label: '已失败', color: '#E11D48', background: '#FFF1F2' },
  ROLLBACK_PREVIEW: { label: '撤销预览中', color: '#D97706', background: '#FFF7E8' },
  ROLLED_BACK: { label: '已撤销', color: '#667085', background: '#F2F4F7' },
}

const modeMap: Record<string, string> = {
  INITIALIZE: '首次初始化',
  SYNC: '后续同步',
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

const issueSeverityMap: Record<string, { label: string; color: string; background: string }> = {
  BLOCKER: { label: '阻断', color: '#E11D48', background: '#FFF1F2' },
  WARNING: { label: '提醒', color: '#D97706', background: '#FFF7E8' },
}

const resolutionStatusMap: Record<string, string> = {
  PENDING: '待处理',
  RESOLVED: '已处理',
  IGNORED: '已忽略',
  DEFERRED: '稍后处理',
}

function getBatchStatusInfo(status: string): { label: string; color: string; background: string } {
  return batchStatusMap[status] || { label: status, color: '#98A2B3', background: '#F2F4F7' }
}

// Summary items for display
const summaryItems = computed(() => {
  if (!batchDetail.value) return []
  const d = batchDetail.value
  return [
    { label: '新增', count: d.new_count || 0, color: '#16825D' },
    { label: '更新', count: d.update_count || 0, color: '#2563EB' },
    { label: '待确认', count: d.confirmation_count || 0, color: '#D97706' },
    { label: '错误', count: d.error_count || 0, color: '#E11D48' },
    { label: '无变化', count: d.unchanged_count || 0, color: '#667085' },
    { label: '跳过', count: d.skipped_count || 0, color: '#98A2B3' },
  ].filter(item => item.count > 0)
})

const totalPages = computed(() => Math.ceil(totalRows.value / rowPageSize))

onMounted(async () => {
  await loadBatchDetail().catch(() => {})
  // 同时加载数据行和问题，确保进入页面时两个标签都有数据
  loadRows()
  loadIssues()
})

async function loadBatchDetail() {
  loading.value = true
  try {
    const detail = await getBatchDetail(batchId.value)
    batchDetail.value = detail
  } catch (e: any) {
    showToast({ message: e.message || '加载详情失败', type: 'error' })
  } finally {
    loading.value = false
  }
}

async function loadRows() {
  loadingRows.value = true
  try {
    const params: Record<string, any> = { page: rowPage.value, page_size: rowPageSize }
    if (rowFilterStatus.value) params.status = rowFilterStatus.value
    const result = await getBatchRows(batchId.value, params)
    rows.value = result.items || []
    totalRows.value = result.total
  } catch (e: any) {
    showToast({ message: e.message || '加载行数据失败', type: 'error' })
  } finally {
    loadingRows.value = false
  }
}

async function loadIssues() {
  loadingIssues.value = true
  try {
    const result = await getBatchIssues(batchId.value)
    issues.value = result.items || []
    issueTotal.value = result.total || 0
    issuePendingCount.value = result.pending_count || 0
    issueResolvedCount.value = result.resolved_count || 0
    issueIgnoredCount.value = result.ignored_count || 0
  } catch (e: any) {
    showToast({ message: e.message || '加载问题失败', type: 'error' })
  } finally {
    loadingIssues.value = false
  }
}

function onTabChange(tab: 'rows' | 'issues') {
  activeTab.value = tab
  if (tab === 'rows' && rows.value.length === 0) {
    loadRows()
  }
  if (tab === 'issues' && issues.value.length === 0) {
    loadIssues()
  }
}

function onFilterChange(status: string) {
  rowFilterStatus.value = status
  rowPage.value = 1
  loadRows()
}

function onPageChange(delta: number) {
  rowPage.value += delta
  loadRows()
}

function downloadFile() {
  const url = getFileDownloadUrl(batchId.value)
  window.open(url, '_blank')
}

function handleRollbackPreview() {
  confirm({
    title: '撤销预览',
    message: '获取撤销预览信息？',
    confirmText: '预览撤销',
    onConfirm: async () => {
      try {
        const preview = await getRollbackPreview(batchId.value)
        rollbackPreview.value = preview
        showRollbackPreview.value = true

        if (!preview.can_rollback) {
          showToast({ message: '该批次无法撤销：存在不可逆操作', type: 'warning' })
          return
        }
      } catch (e: any) {
        showToast({ message: e.message || '获取撤销预览失败', type: 'error' })
      }
    },
  })
}

function handleRollback() {
  if (!rollbackPreview.value?.can_rollback) {
    showToast({ message: '该批次无法撤销', type: 'warning' })
    return
  }
  confirm({
    title: '确认撤销导入',
    message: `此操作将撤销本次导入的部分或全部操作。已确认的事项不受影响。`,
    confirmText: '确认撤销',
    danger: true,
    onConfirm: async () => {
      try {
        await executeRollback(batchId.value)
        showToast({ message: '撤销成功', type: 'success' })
        showRollbackPreview.value = false
        await loadBatchDetail()
      } catch (e: any) {
        showToast({ message: e.message || '撤销失败', type: 'error' })
      }
    },
  })
}

async function handleSyncConfirmations() {
  try {
    const result = await syncConfirmations(batchId.value)
    syncResult.value = result
    showSyncResult.value = true

    if (result.created_confirmation_count > 0) {
      showToast({
        message: `已创建 ${result.created_confirmation_count} 条待确认事项`,
        type: 'success',
      })
    } else if (result.existing_confirmation_count > 0) {
      showToast({ message: `已有 ${result.existing_confirmation_count} 条待确认事项`, type: 'info' })
    } else {
      showToast({ message: '无需同步', type: 'info' })
    }

    await loadIssues()
    await loadBatchDetail()
  } catch (e: any) {
    showToast({ message: e.message || '同步失败', type: 'error' })
  } finally {
    syncing.value = false
  }
}

function canSyncConfirmations(): boolean {
  const status = batchDetail.value?.batch_status
  if (status !== 'SUCCEEDED') return false
  if (issuePendingCount.value <= 0) return false
  if (syncResult.value && syncResult.value.created_confirmation_count > 0) return false
  return true
}

function goToWizard() {
  router.push(`/roster-imports/new?batch_id=${batchId.value}`)
}

// 多状态标签映射
const multiStatusMap: Record<string, { label: string; color: string; background: string }> = {
  NEW: { label: '新增', color: '#16825D', background: '#EAF8F1' },
  UPDATE: { label: '更新', color: '#2563EB', background: '#EFF6FF' },
  SKIP: { label: '跳过', color: '#98A2B3', background: '#F2F4F7' },
  IMPORTED: { label: '已导入', color: '#16825D', background: '#EAF8F1' },
  CLEAN: { label: '无问题', color: '#16825D', background: '#EAF8F1' },
  NEEDS_CONFIRMATION: { label: '待确认', color: '#D97706', background: '#FFF7E8' },
  ERROR: { label: '错误', color: '#E11D48', background: '#FFF1F2' },
  RESOLVED: { label: '已解决', color: '#16825D', background: '#EAF8F1' },
  IGNORED: { label: '已忽略', color: '#98A2B3', background: '#F2F4F7' },
  PENDING: { label: '待处理', color: '#D97706', background: '#FFF7E8' },
  FAILED: { label: '失败', color: '#E11D48', background: '#FFF1F2' },
  UNCHANGED: { label: '无变化', color: '#667085', background: '#F2F4F7' },
}

function getStatusTags(row: Record<string, any>): Array<{ label: string; color: string; background: string }> {
  const tags: Array<{ label: string; color: string; background: string }> = []

  // import_action tag
  if (row.import_action && multiStatusMap[row.import_action]) {
    tags.push(multiStatusMap[row.import_action])
  }

  // execution_status tag
  if (row.execution_status === 'IMPORTED') {
    tags.push({ label: '已导入', color: '#16825D', background: '#EAF8F1' })
  } else if (row.execution_status === 'PENDING') {
    tags.push({ label: '待处理', color: '#D97706', background: '#FFF7E8' })
  } else if (row.execution_status === 'SKIPPED') {
    tags.push({ label: '跳过', color: '#98A2B3', background: '#F2F4F7' })
  }

  // review_status tag
  if (row.review_status === 'NEEDS_CONFIRMATION' || row.review_status === 'PENDING') {
    tags.push({ label: '待确认', color: '#D97706', background: '#FFF7E8' })
  } else if (row.review_status === 'ERROR') {
    tags.push({ label: '错误', color: '#E11D48', background: '#FFF1F2' })
  } else if (row.review_status === 'IGNORED') {
    tags.push({ label: '已忽略', color: '#98A2B3', background: '#F2F4F7' })
  }

  // fall back to old row_status if no new status tags
  if (tags.length === 0 && row.row_status === 'NEEDS_CONFIRMATION') {
    tags.push({ label: '待确认', color: '#D97706', background: '#FFF7E8' })
  } else if (tags.length === 0 && row.row_status === 'ERROR') {
    tags.push({ label: '错误', color: '#E11D48', background: '#FFF1F2' })
  }

  return tags
}

// Revalidation
async function handleRevalidate() {
  revalidating.value = true
  try {
    const result = await revalidateBatch(batchId.value)
    revalidationResult.value = result
    showRevalidation.value = true
  } catch (e: any) {
    showToast({ message: e.message || '重新校验失败', type: 'error' })
  } finally {
    revalidating.value = false
  }
}

async function handleRepair() {
  if (!revalidationResult.value?.stats?.auto_repairable) {
    showToast({ message: '没有可以自动修复的员工', type: 'info' })
    return
  }
  confirm({
    title: '确认执行修复',
    message: `将自动修复 ${revalidationResult.value.stats.auto_repairable} 名员工的${revalidationResult.value.stats.wrong_probation_count ? `（${revalidationResult.value.stats.wrong_probation_count} 名试用期状态、${revalidationResult.value.stats.missing_regularization_date_count} 名缺少转正日期）` : ''}数据。此操作不可逆，是否继续？`,
    confirmText: '执行修复',
    danger: true,
    onConfirm: async () => {
      repairing.value = true
      try {
        const result = await repairBatch(batchId.value)
        repairResult.value = result
        showToast({ message: `修复完成：修复 ${result.repaired_count} 人，取消 ${result.cancelled_tasks_count || 0} 个任务，创建 ${result.confirmations_created || 0} 个确认事项`, type: 'success' })
        showRevalidation.value = false
        await loadBatchDetail()
      } catch (e: any) {
        showToast({ message: e.message || '修复失败', type: 'error' })
      } finally {
        repairing.value = false
      }
    },
  })
}

function goBack() {
  router.push('/roster-imports')
}

// Row filter options
const rowFilterOptions = [
  { label: '全部', value: '' },
  { label: '新增', value: 'NEW' },
  { label: '更新', value: 'UPDATE' },
  { label: '待确认', value: 'NEEDS_CONFIRMATION' },
  { label: '错误', value: 'ERROR' },
  { label: '无变化', value: 'UNCHANGED' },
  { label: '跳过', value: 'SKIPPED' },
  { label: '已导入', value: 'IMPORTED' },
]
</script>

<template>
  <div class="page">
    <!-- Header -->
    <PageHeader
      title="导入详情"
      :subtitle="batchDetail?.file_name || ''"
      :show-back="true"
      :badge-text="batchDetail ? getBatchStatusInfo(batchDetail.batch_status || batchDetail.status || '').label : ''"
      :badge-variant="batchDetail ? (batchDetail.batch_status === 'SUCCEEDED' ? 'success' : batchDetail.batch_status === 'FAILED' ? 'danger' : 'info') : 'neutral'"
      @back="goBack"
    >
      <template #actions>
        <BaseButton variant="ghost" size="sm" @click="downloadFile">
          <Download :size="16" />
          下载原文件
        </BaseButton>
        <BaseButton
          v-if="batchDetail?.batch_status === 'SUCCEEDED'"
          variant="warning"
          size="sm"
          :loading="revalidating"
          @click="handleRevalidate"
        >
          <AlertTriangle :size="16" />
          重新校验
        </BaseButton>
        <BaseButton
          v-if="batchDetail?.batch_status === 'SUCCEEDED'"
          variant="warning"
          size="sm"
          @click="handleRollbackPreview"
        >
          <RotateCcw :size="16" />
          撤销导入
        </BaseButton>
      </template>
    </PageHeader>

    <div v-if="!batchDetail && loading" class="loading-state text-tertiary">加载中...</div>

    <!-- Batch Info Card -->
    <div v-if="batchDetail" class="card detail-section">
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">批次号</span>
          <span class="info-value mono">{{ batchDetail.batch_no || '—' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">文件名</span>
          <span class="info-value">
            <FileText :size="14" class="info-icon" />
            {{ batchDetail.file_name || '—' }}
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">导入模式</span>
          <span class="info-value">{{ getStatusLabel(modeMap, batchDetail.mode) || '—' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">工作表</span>
          <span class="info-value">{{ batchDetail.sheet_name || '—' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">总行数</span>
          <span class="info-value">{{ batchDetail.total_rows || 0 }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">SHA-256</span>
          <span class="info-value mono small-text">{{ batchDetail.file_sha256 ? batchDetail.file_sha256.substring(0, 16) + '...' : '—' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">创建时间</span>
          <span class="info-value">{{ formatDateTime(batchDetail.created_at) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">完成时间</span>
          <span class="info-value">{{ batchDetail.completed_at ? formatDateTime(batchDetail.completed_at) : '—' }}</span>
        </div>
      </div>

      <!-- Failure message -->
      <div v-if="batchDetail.failure_message" class="alert alert-danger">
        <AlertCircle :size="16" />
        <span>{{ batchDetail.failure_message }}</span>
      </div>
    </div>

    <!-- Summary cards -->
    <div v-if="summaryItems.length > 0" class="summary-cards">
      <div
        v-for="item in summaryItems"
        :key="item.label"
        class="summary-card"
        :style="{ borderTopColor: item.color }"
      >
        <div class="summary-count" :style="{ color: item.color }">{{ item.count }}</div>
        <div class="summary-label">{{ item.label }}</div>
      </div>
    </div>

    <!-- Actions -->
    <div v-if="batchDetail" class="action-bar">
      <BaseButton variant="secondary" size="sm" @click="downloadFile">
        <Download :size="14" />
        下载原文件
      </BaseButton>
      <BaseButton
        v-if="batchDetail.batch_status === 'SUCCEEDED'"
        variant="warning"
        size="sm"
        @click="handleRollbackPreview"
      >
        <RotateCcw :size="14" />
        撤销导入
      </BaseButton>
    </div>

    <!-- Tabs: Rows / Issues -->
    <div v-if="batchDetail" class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'rows' }"
        @click="onTabChange('rows')"
      >
        <List :size="14" />
        数据行
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'issues' }"
        @click="onTabChange('issues')"
      >
        <AlertTriangle :size="14" />
        问题（{{ issueTotal }}）
        <span v-if="issuePendingCount > 0" class="tab-badge">{{ issuePendingCount }} 待处理</span>
      </button>
    </div>

    <!-- Rows tab -->
    <div v-if="activeTab === 'rows'" class="card table-card">
      <!-- Row filters -->
      <div class="row-filters">
        <button
          v-for="opt in rowFilterOptions"
          :key="opt.value"
          class="filter-tab"
          :class="{ active: rowFilterStatus === opt.value }"
          @click="onFilterChange(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>

      <table v-if="rows.length > 0">
        <thead>
          <tr>
            <th>行号</th>
            <th>姓名</th>
            <th>匹配员工 ID</th>
            <th>匹配方式</th>
            <th>状态</th>
            <th>原始数据</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id || row.row_no">
            <td class="td-row-no">{{ row.row_no }}</td>
            <td class="td-name">{{ row.normalized_name || '—' }}</td>
            <td class="td-employee-id">
              <span v-if="row.employee_id" class="mono">{{ row.employee_id }}</span>
              <span v-else class="text-tertiary">—</span>
            </td>
            <td>{{ row.match_type || '—' }}</td>
            <td>
              <div class="multi-status-tags">
                <BaseBadge
                  v-for="(tag, idx) in getStatusTags(row)"
                  :key="idx"
                  type="custom"
                  :label="tag.label"
                  :color="tag.color"
                  :background="tag.background"
                  size="sm"
                />
              </div>
            </td>
            <td class="td-raw">
              <span v-if="row.raw_data" class="raw-preview">{{ JSON.stringify(row.raw_data).substring(0, 60) }}{{ JSON.stringify(row.raw_data).length > 60 ? '...' : '' }}</span>
              <span v-else class="text-tertiary">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loadingRows">
        <BaseEmpty title="暂无数据行" />
      </div>
      <div v-else class="loading-state text-tertiary">加载中...</div>

      <!-- Pagination -->
      <div v-if="totalRows > rowPageSize" class="pagination-bar">
        <div class="text-sm text-tertiary">共 {{ totalRows }} 条</div>
        <div class="pagination-controls">
          <button :disabled="rowPage <= 1" class="page-btn" @click="onPageChange(-1)">上一页</button>
          <span class="page-info">{{ rowPage }} / {{ totalPages }}</span>
          <button :disabled="rowPage >= totalPages" class="page-btn" @click="onPageChange(1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- Issues tab -->
    <div v-if="activeTab === 'issues'" class="card issues-card">
      <!-- Toolbar -->
      <div class="issues-toolbar">
        <div class="issues-stats">
          <span class="stat-item">总计 {{ issueTotal }} 条</span>
          <span v-if="issuePendingCount > 0" class="stat-item stat-pending">待处理 {{ issuePendingCount }}</span>
          <span v-if="issueResolvedCount > 0" class="stat-item stat-resolved">已处理 {{ issueResolvedCount }}</span>
          <span v-if="issueIgnoredCount > 0" class="stat-item stat-ignored">已忽略 {{ issueIgnoredCount }}</span>
        </div>
        <div class="issues-toolbar-actions">
          <!-- 未提交批次 → 去导入向导 -->
          <BaseButton
            v-if="batchDetail && !['SUCCEEDED', 'FAILED', 'ROLLED_BACK'].includes(batchDetail.batch_status) && issuePendingCount > 0"
            variant="primary"
            size="sm"
            @click="goToWizard"
          >
            去导入向导处理
          </BaseButton>
          <!-- 已成功批次 → 同步待确认事项 -->
          <BaseButton
            v-if="canSyncConfirmations()"
            variant="primary"
            size="sm"
            :loading="syncing"
            @click="handleSyncConfirmations"
          >
            <Check :size="14" />
            同步待确认事项
          </BaseButton>
        </div>
      </div>

      <div v-if="issues.length > 0">
        <!-- BLOCKER issues -->
        <div v-if="issues.filter(i => i.severity === 'BLOCKER').length > 0" class="issue-group">
          <h3 class="issue-group-title">
            <AlertCircle :size="16" class="issue-error-icon" />
            阻断问题
          </h3>
          <div
            v-for="issue in issues.filter(i => i.severity === 'BLOCKER')"
            :key="issue.id"
            class="issue-item issue-blocker"
          >
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <div class="issue-meta">
                <BaseBadge
                  type="custom"
                  label="BLOCKER"
                  color="#E11D48"
                  background="#FFF1F2"
                  size="sm"
                />
                <BaseBadge
                  type="custom"
                  :label="getStatusLabel(resolutionStatusMap, issue.resolution_status) || issue.resolution_status"
                  :color="issue.resolution_status === 'PENDING' ? '#D97706' : '#16825D'"
                  :background="issue.resolution_status === 'PENDING' ? '#FFF7E8' : '#EAF8F1'"
                  size="sm"
                />
              </div>
            </div>
            <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
            <div v-if="issue.old_value !== null || issue.new_value !== null" class="issue-values">
              <div v-if="issue.old_value !== null" class="value-pair">
                <span class="value-label">当前值：</span>
                <span class="value-old">{{ String(issue.old_value) }}</span>
              </div>
              <div v-if="issue.new_value !== null" class="value-pair">
                <span class="value-label">新值：</span>
                <span class="value-new">{{ String(issue.new_value) }}</span>
              </div>
            </div>
            <div class="issue-footer">
              <span v-if="issue.resolution_action" class="resolution-info">
                处理方式：{{ issue.resolution_action }}
              </span>
              <span v-if="issue.resolved_at" class="resolution-time">
                处理时间：{{ formatDateTime(issue.resolved_at) }}
              </span>
            </div>
          </div>
        </div>

        <!-- WARNING issues -->
        <div v-if="issues.filter(i => i.severity === 'WARNING').length > 0" class="issue-group">
          <h3 class="issue-group-title">
            <AlertTriangle :size="16" class="issue-warn-icon" />
            提醒
          </h3>
          <div
            v-for="issue in issues.filter(i => i.severity === 'WARNING')"
            :key="issue.id"
            class="issue-item issue-warning"
          >
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <div class="issue-meta">
                <BaseBadge
                  type="custom"
                  label="WARNING"
                  color="#D97706"
                  background="#FFF7E8"
                  size="sm"
                />
                <BaseBadge
                  type="custom"
                  :label="getStatusLabel(resolutionStatusMap, issue.resolution_status) || issue.resolution_status"
                  :color="issue.resolution_status === 'PENDING' ? '#D97706' : '#16825D'"
                  :background="issue.resolution_status === 'PENDING' ? '#FFF7E8' : '#EAF8F1'"
                  size="sm"
                />
              </div>
            </div>
            <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
            <div v-if="issue.old_value !== null || issue.new_value !== null" class="issue-values">
              <div v-if="issue.old_value !== null" class="value-pair">
                <span class="value-label">当前值：</span>
                <span class="value-old">{{ String(issue.old_value) }}</span>
              </div>
              <div v-if="issue.new_value !== null" class="value-pair">
                <span class="value-label">新值：</span>
                <span class="value-new">{{ String(issue.new_value) }}</span>
              </div>
            </div>
            <div class="issue-footer">
              <span v-if="issue.resolution_action" class="resolution-info">
                处理方式：{{ issue.resolution_action }}
              </span>
              <span v-if="issue.resolved_at" class="resolution-time">
                处理时间：{{ formatDateTime(issue.resolved_at) }}
              </span>
            </div>
          </div>
        </div>

        <!-- INFO issues -->
        <div v-if="issues.filter(i => i.severity === 'INFO').length > 0" class="issue-group">
          <h3 class="issue-group-title">
            <AlertCircle :size="16" class="issue-info-icon" />
            提示信息
          </h3>
          <div
            v-for="issue in issues.filter(i => i.severity === 'INFO')"
            :key="issue.id"
            class="issue-item issue-info"
          >
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <div class="issue-meta">
                <BaseBadge
                  type="custom"
                  label="INFO"
                  color="#2563EB"
                  background="#EFF6FF"
                  size="sm"
                />
                <BaseBadge
                  type="custom"
                  :label="getStatusLabel(resolutionStatusMap, issue.resolution_status) || issue.resolution_status"
                  :color="issue.resolution_status === 'PENDING' ? '#D97706' : '#16825D'"
                  :background="issue.resolution_status === 'PENDING' ? '#FFF7E8' : '#EAF8F1'"
                  size="sm"
                />
              </div>
            </div>
            <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
            <div class="issue-footer">
              <span v-if="issue.resolution_action" class="resolution-info">
                处理方式：{{ issue.resolution_action }}
              </span>
              <span v-if="issue.resolved_at" class="resolution-time">
                处理时间：{{ formatDateTime(issue.resolved_at) }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="!loadingIssues">
        <BaseEmpty title="暂无问题" />
      </div>
      <div v-else class="loading-state text-tertiary">加载中...</div>
    </div>

    <!-- Rollback Preview Modal -->
    <BaseModal
      v-if="showRollbackPreview && rollbackPreview"
      :show="showRollbackPreview"
      title="撤销预览"
      :message="rollbackPreview.can_rollback ? `可撤销 ${rollbackPreview.items.filter(i => i.reversible).length} 项，不可撤销 ${rollbackPreview.irreversible_operations.length} 项。` : '该批次无法撤销'"
      :confirm-text="rollbackPreview.can_rollback ? '执行撤销' : '关闭'"
      :danger="rollbackPreview.can_rollback"
      @confirm="rollbackPreview.can_rollback ? handleRollback() : (showRollbackPreview = false)"
      @cancel="showRollbackPreview = false"
    >
      <template #message>
        <div class="rollback-preview-body">
          <p v-if="!rollbackPreview.can_rollback" class="text-danger">
            存在不可逆操作，无法撤销本次导入。
          </p>

          <!-- Rollback items -->
          <div v-if="rollbackPreview.items.length > 0" class="rollback-items">
            <div
              v-for="item in rollbackPreview.items"
              :key="item.employee_id"
              class="rollback-item"
              :class="{ 'rollback-conflict': item.conflict }"
            >
              <div class="rollback-item-header">
                <span class="rollback-employee">{{ item.employee_name }}</span>
                <span class="rollback-action">{{ item.action }}</span>
                <BaseBadge
                  type="custom"
                  :label="item.reversible ? '可撤销' : '不可撤销'"
                  :color="item.reversible ? '#16825D' : '#E11D48'"
                  :background="item.reversible ? '#EAF8F1' : '#FFF1F2'"
                  size="sm"
                />
              </div>
              <p class="rollback-detail">{{ item.details }}</p>
              <p v-if="item.conflict && item.conflict_reason" class="rollback-conflict-reason">
                <AlertTriangle :size="12" />
                {{ item.conflict_reason }}
              </p>
            </div>
          </div>

          <!-- Irreversible operations -->
          <div v-if="rollbackPreview.irreversible_operations.length > 0" class="irreversible-section">
            <h4 class="irreversible-title">不可撤销的操作</h4>
            <ul class="irreversible-list">
              <li v-for="(op, idx) in rollbackPreview.irreversible_operations" :key="idx">
                {{ op }}
              </li>
            </ul>
          </div>

          <!-- Conflicts -->
          <div v-if="rollbackPreview.conflicts.length > 0" class="conflict-section">
            <h4 class="conflict-title">冲突项</h4>
            <ul class="conflict-list">
              <li v-for="(conflict, idx) in rollbackPreview.conflicts" :key="idx">
                <AlertTriangle :size="12" />
                {{ conflict }}
              </li>
            </ul>
          </div>
        </div>
      </template>
    </BaseModal>

    <!-- Revalidation Modal -->
    <BaseModal
      v-if="showRevalidation && revalidationResult"
      :show="showRevalidation"
      title="重新校验结果"
      :confirm-text="revalidationResult.stats?.auto_repairable > 0 ? '执行自动修复' : '关闭'"
      :danger="revalidationResult.stats?.auto_repairable > 0"
      :loading="repairing"
      @confirm="revalidationResult.stats?.auto_repairable > 0 ? handleRepair() : (showRevalidation = false)"
      @cancel="showRevalidation = false"
    >
      <template #message>
        <div class="revalidation-body">
          <div class="revalidation-summary">
            <div class="rev-stat">
              <span class="rev-stat-count">{{ revalidationResult.stats?.total_rows || 0 }}</span>
              <span class="rev-stat-label">总行数</span>
            </div>
            <div class="rev-stat">
              <span class="rev-stat-count" style="color: #D97706">{{ revalidationResult.stats?.issues_found || 0 }}</span>
              <span class="rev-stat-label">发现问题</span>
            </div>
            <div class="rev-stat">
              <span class="rev-stat-count" style="color: #16825D">{{ revalidationResult.stats?.auto_repairable || 0 }}</span>
              <span class="rev-stat-label">可自动修复</span>
            </div>
            <div class="rev-stat">
              <span class="rev-stat-count" style="color: #E11D48">{{ revalidationResult.stats?.needs_manual_review || 0 }}</span>
              <span class="rev-stat-label">需人工处理</span>
            </div>
          </div>

          <div v-if="revalidationResult.stats?.wrong_probation_count" class="rev-detail">
            <p><strong>错误的试用期状态：</strong>{{ revalidationResult.stats.wrong_probation_count }} 人</p>
          </div>
          <div v-if="revalidationResult.stats?.missing_regularization_date_count" class="rev-detail">
            <p><strong>缺少转正日期：</strong>{{ revalidationResult.stats.missing_regularization_date_count }} 人</p>
          </div>

          <div v-if="revalidationResult.employee_findings?.length > 0" class="rev-findings">
            <h4 class="rev-findings-title">员工详情</h4>
            <div
              v-for="f in revalidationResult.employee_findings.filter((f: Record<string, any>) => f.differences?.length > 0)"
              :key="f.employee_id || f.row_no"
              class="rev-finding"
            >
              <div class="rev-finding-header">
                <span class="rev-finding-name">{{ f.employee_name || '未知' }}</span>
                <BaseBadge
                  v-if="f.can_auto_repair"
                  type="custom"
                  label="可自动修复"
                  color="#16825D"
                  background="#EAF8F1"
                  size="sm"
                />
                <BaseBadge
                  v-else
                  type="custom"
                  :label="f.cannot_repair_reason || '需人工'"
                  color="#E11D48"
                  background="#FFF1F2"
                  size="sm"
                />
              </div>
              <div v-for="diff in f.differences" :key="diff.field" class="rev-diff">
                <span class="rev-diff-field">{{ diff.field }}：</span>
                <span class="rev-diff-from">{{ diff.current }}</span>
                <span class="rev-diff-arrow">→</span>
                <span class="rev-diff-to">{{ diff.expected }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </BaseModal>

    <!-- Confirm modal -->
    <BaseModal
      :show="showConfirm"
      :title="confirmOpts.title"
      :message="confirmOpts.message"
      :confirm-text="confirmOpts.confirmText"
      :danger="confirmOpts.danger"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>

<style scoped>
/* Card */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.detail-section {
  padding: 20px 24px;
  margin-bottom: 16px;
}

/* Info Grid */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.info-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  font-weight: 500;
}
.info-value {
  font-size: var(--font-size-sm);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.info-icon {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.mono {
  font-family: monospace;
}
.small-text {
  font-size: var(--font-size-xs);
}

/* Alert */
.alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  margin-top: 16px;
}
.alert-danger {
  background: var(--color-danger-soft);
  color: #BE123C;
  border: 1px solid #FECDD3;
}

/* Summary */
.summary-cards {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.summary-card {
  flex: 1;
  min-width: 90px;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-top: 3px solid;
  text-align: center;
  background: var(--color-surface);
}
.summary-count {
  font-size: var(--font-size-lg);
  font-weight: 700;
  line-height: 1.2;
}
.summary-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 2px;
}

/* Action bar */
.action-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: 16px;
}
.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-bottom: none;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.15s;
}
.tab.active {
  background: var(--color-surface);
  color: var(--color-primary);
  font-weight: 600;
}
.tab:hover:not(.active) {
  background: var(--color-surface-secondary);
}

/* Table */
.table-card {
  overflow: hidden;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
th {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-secondary);
}
tr:hover td {
  background: var(--color-bg);
}
.td-row-no {
  font-family: monospace;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}
.td-name {
  font-weight: 500;
}
.td-employee-id {
  font-family: monospace;
  font-size: var(--font-size-xs);
}
.td-raw {
  max-width: 200px;
}
.raw-preview {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  font-family: monospace;
}

/* Row filters */
.row-filters {
  display: flex;
  gap: 4px;
  padding: 10px 12px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--color-border);
}
.filter-tab {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: var(--color-surface);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all 0.15s;
}
.filter-tab:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.filter-tab.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

/* Pagination */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}
.pagination-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.page-btn {
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  cursor: pointer;
  font-size: var(--font-size-sm);
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-info {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* Issues */
.issues-card {
  padding: 0;
}
.issues-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}
.issues-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
}
.stat-item { color: var(--color-text-secondary); }
.stat-pending { color: var(--color-warning, #d97706); font-weight: 500; }
.stat-resolved { color: var(--color-success, #16825D); font-weight: 500; }
.stat-ignored { color: var(--color-text-tertiary); }

.tab-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 500;
  color: #fff;
  background: var(--color-warning, #d97706);
  border-radius: 10px;
  margin-left: 4px;
}

.issue-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.issue-group {
  padding: 16px 20px;
}
.issue-group + .issue-group {
  border-top: 1px solid var(--color-border);
}
.issue-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-base);
  font-weight: 600;
  margin-bottom: 12px;
}
.issue-error-icon {
  color: var(--color-danger);
}
.issue-warn-icon {
  color: var(--color-warning);
}
.issue-info-icon {
  color: var(--color-primary);
}
.issue-item {
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
}
.issue-blocker {
  border-left: 3px solid var(--color-danger);
}
.issue-warning {
  border-left: 3px solid var(--color-warning);
}
.issue-info {
  border-left: 3px solid var(--color-primary);
}
.issue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.issue-meta {
  display: flex;
  gap: 6px;
}
.issue-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.issue-message {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.issue-values {
  display: flex;
  gap: 16px;
  margin-bottom: 6px;
  font-size: var(--font-size-xs);
}
.value-pair {
  display: flex;
  gap: 4px;
  align-items: center;
}
.value-label {
  color: var(--color-text-tertiary);
}
.value-old {
  color: var(--color-text-secondary);
  text-decoration: line-through;
}
.value-new {
  color: var(--color-primary);
  font-weight: 500;
}
.issue-footer {
  display: flex;
  gap: 16px;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

/* Rollback Preview */
.rollback-preview-body {
  max-height: 400px;
  overflow-y: auto;
}
.rollback-items {
  margin-top: 12px;
}
.rollback-item {
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
}
.rollback-conflict {
  border-color: var(--color-danger-soft);
  background: var(--color-danger-soft);
}
.rollback-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.rollback-employee {
  font-weight: 500;
  font-size: var(--font-size-sm);
}
.rollback-action {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.rollback-detail {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.rollback-conflict-reason {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--color-danger);
  margin-top: 4px;
}
.irreversible-section,
.conflict-section {
  margin-top: 12px;
}
.irreversible-title,
.conflict-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
}
.irreversible-list,
.conflict-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.irreversible-list li,
.conflict-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  padding: 4px 0;
}

/* Multi-status tags */
.multi-status-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

/* Revalidation */
.revalidation-body {
  max-height: 500px;
  overflow-y: auto;
}
.revalidation-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.rev-stat {
  flex: 1;
  min-width: 80px;
  text-align: center;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.rev-stat-count {
  display: block;
  font-size: 20px;
  font-weight: 700;
}
.rev-stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.rev-detail {
  font-size: var(--font-size-sm);
  margin-bottom: 8px;
}
.rev-findings {
  margin-top: 12px;
}
.rev-findings-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin-bottom: 8px;
}
.rev-finding {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
}
.rev-finding-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.rev-finding-name {
  font-weight: 500;
  font-size: var(--font-size-sm);
}
.rev-diff {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.rev-diff-field {
  font-weight: 500;
}
.rev-diff-from {
  color: var(--color-danger);
  text-decoration: line-through;
}
.rev-diff-arrow {
  color: var(--color-text-tertiary);
}
.rev-diff-to {
  color: var(--color-primary);
  font-weight: 500;
}

/* Utility */
.text-danger {
  color: var(--color-danger);
}
.text-tertiary {
  color: var(--color-text-tertiary);
}
.loading-state {
  padding: 48px;
  text-align: center;
}
</style>
