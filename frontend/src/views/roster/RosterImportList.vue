<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Upload, FileText, Download, Eye, RotateCcw, AlertTriangle } from 'lucide-vue-next'
import { formatDateTime } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { getStatusLabel } from '@/constants/status'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import { listBatches, getRollbackPreview, executeRollback, getFileDownloadUrl } from '@/services/rosterImportService'
import type { BatchListItem } from '@/types/roster-import'

const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const batches = ref<BatchListItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20

// 导入批次状态映射
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

// 导入模式映射
const modeMap: Record<string, string> = {
  INITIALIZE: '首次初始化',
  SYNC: '后续同步',
}

function getBatchStatusInfo(status: string): { label: string; color: string; background: string } {
  return batchStatusMap[status] || { label: status, color: '#98A2B3', background: '#F2F4F7' }
}

onMounted(async () => {
  await loadBatches()
})

async function loadBatches() {
  loading.value = true
  try {
    const res = await listBatches({ page: page.value, page_size: pageSize })
    batches.value = res.items
    total.value = res.total
  } catch (e: any) {
    showToast({ message: e.message || '加载导入记录失败', type: 'error' })
  } finally {
    loading.value = false
  }
}

function goToNew() {
  router.push('/roster-imports/new')
}

function goToDetail(batch: BatchListItem) {
  router.push(`/roster-imports/${batch.id}`)
}

function downloadFile(batch: BatchListItem) {
  const url = getFileDownloadUrl(batch.id)
  window.open(url, '_blank')
}

function previewRollback(batch: BatchListItem) {
  confirm({
    title: '撤销预览',
    message: `确定要预览批次「${batch.file_name}」的撤销操作吗？`,
    confirmText: '预览撤销',
    onConfirm: async () => {
      try {
        const preview = await getRollbackPreview(batch.id)
        if (!preview.can_rollback) {
          showToast({ message: '该批次无法撤销：存在不可逆操作', type: 'warning' })
          return
        }
        const revCount = preview.items.filter(i => i.reversible).length
        const irrCount = preview.irreversible_operations.length
        // 确认撤销
        confirm({
          title: '确认撤销导入',
          message: `将撤销 ${revCount} 项操作，${irrCount} 项不可撤销操作不会受影响。此操作不可恢复。`,
          confirmText: '确认撤销',
          danger: true,
          onConfirm: async () => {
            try {
              await executeRollback(batch.id)
              showToast({ message: '撤销成功', type: 'success' })
              await loadBatches()
            } catch (e2: any) {
              showToast({ message: e2.message || '撤销失败', type: 'error' })
            }
          },
        })
      } catch (e: any) {
        showToast({ message: e.message || '获取撤销预览失败', type: 'error' })
      }
    },
  })
}

const totalPages = computed(() => Math.ceil(total.value / pageSize))
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <div class="page-intro-left">
        <h1 class="page-title">花名册导入</h1>
        <p class="page-subtitle">上传 Excel 花名册，批量导入和更新员工信息</p>
      </div>
      <BaseButton variant="primary" @click="goToNew">
        <Upload :size="16" />
        新建导入
      </BaseButton>
    </div>

    <!-- Table -->
    <div class="card table-card">
      <table v-if="batches.length > 0">
        <thead>
          <tr>
            <th>批次号</th>
            <th>文件名</th>
            <th>模式</th>
            <th>状态</th>
            <th>总数</th>
            <th>新增</th>
            <th>更新</th>
            <th>跳过</th>
            <th>待确认</th>
            <th>错误</th>
            <th>导入时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="batch in batches" :key="batch.id" class="batch-row">
            <td class="td-batch-no">{{ batch.batch_no }}</td>
            <td class="td-file-name" :title="batch.file_name">
              <FileText :size="14" class="icon-file" />
              <span>{{ batch.file_name }}</span>
            </td>
            <td>
              <BaseBadge
                type="custom"
                :label="getStatusLabel(modeMap, batch.mode)"
                :color="batch.mode === 'INITIALIZE' ? '#7C3AED' : '#2563EB'"
                :background="batch.mode === 'INITIALIZE' ? '#F3E8FF' : '#EFF6FF'"
                size="sm"
              />
            </td>
            <td>
              <BaseBadge
                type="custom"
                :label="getBatchStatusInfo(batch.batch_status).label"
                :color="getBatchStatusInfo(batch.batch_status).color"
                :background="getBatchStatusInfo(batch.batch_status).background"
                size="sm"
              />
            </td>
            <td>{{ batch.total_rows }}</td>
            <td class="td-num">{{ batch.new_count || 0 }}</td>
            <td class="td-num">{{ batch.update_count || 0 }}</td>
            <td class="td-num">{{ batch.skipped_count || 0 }}</td>
            <td class="td-num">{{ batch.confirmation_count || 0 }}</td>
            <td class="td-num">
              <span v-if="batch.error_count" class="text-danger">{{ batch.error_count }}</span>
              <span v-else>0</span>
            </td>
            <td class="td-time">{{ formatDateTime(batch.created_at) }}</td>
            <td class="td-actions">
              <button class="action-link" title="查看详情" @click="goToDetail(batch)">
                <Eye :size="14" />
              </button>
              <button class="action-link" title="下载文件" @click="downloadFile(batch)">
                <Download :size="14" />
              </button>
              <button
                v-if="batch.batch_status === 'SUCCEEDED'"
                class="action-link"
                title="撤销预览"
                @click="previewRollback(batch)"
              >
                <RotateCcw :size="14" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading">
        <BaseEmpty
          title="暂无导入记录"
          description="点击上方按钮上传花名册文件"
          action-label="新建导入"
          @action="goToNew"
        />
      </div>
      <div v-else class="loading-state text-tertiary">加载中...</div>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="pagination-bar">
      <div class="text-sm text-tertiary">共 {{ total }} 条</div>
      <div class="pagination-controls">
        <button :disabled="page <= 1" class="page-btn" @click="page--; loadBatches()">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" class="page-btn" @click="page++; loadBatches()">下一页</button>
      </div>
    </div>

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
.page-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}
.page-title {
  font-size: var(--font-size-lg);
  font-weight: 700;
  margin-bottom: 4px;
}
.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* Card table */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
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
  white-space: nowrap;
}
.batch-row {
  transition: background 0.15s;
}
.batch-row:hover {
  background: var(--color-bg);
}

.td-batch-no {
  font-family: monospace;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
}
.td-file-name {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.icon-file {
  flex-shrink: 0;
  color: var(--color-text-tertiary);
}
.td-num {
  text-align: center;
}
.td-time {
  white-space: nowrap;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.td-actions {
  white-space: nowrap;
  display: flex;
  gap: 4px;
}
.action-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 4px 6px;
  transition: all 0.15s;
}
.action-link:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.text-danger {
  color: var(--color-danger);
  font-weight: 600;
}

/* Pagination */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 12px 0;
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

.loading-state {
  padding: 48px;
  text-align: center;
}
</style>
