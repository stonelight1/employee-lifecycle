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
import {
  getBatchDetail,
  getBatchRows,
  getBatchIssues,
  getRollbackPreview,
  executeRollback,
  getFileDownloadUrl,
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
    <div class="page-header">
      <button class="back-link" @click="goBack">
        <ChevronLeft :size="16" />
        返回列表
      </button>
      <div class="header-main">
        <div class="header-title-row">
          <h1 class="page-title">导入详情</h1>
          <BaseBadge
            v-if="batchDetail"
            type="custom"
            :label="getBatchStatusInfo(batchDetail.batch_status || batchDetail.status || '').label"
            :color="getBatchStatusInfo(batchDetail.batch_status || batchDetail.status || '').color"
            :background="getBatchStatusInfo(batchDetail.batch_status || batchDetail.status || '').background"
            size="md"
          />
        </div>
      </div>
    </div>

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
        问题（{{ issues.length }}）
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
              <BaseBadge
                type="custom"
                :label="rowStatusInfo[row.row_status]?.label || row.row_status"
                :color="rowStatusInfo[row.row_status]?.color || '#98A2B3'"
                :background="rowStatusInfo[row.row_status]?.background || '#F2F4F7'"
                size="sm"
              />
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
.page-header {
  margin-bottom: 20px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  margin-bottom: 8px;
}
.back-link:hover {
  color: var(--color-primary);
}
.header-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  font-size: var(--font-size-lg);
  font-weight: 700;
}

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
