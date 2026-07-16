<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listConfirmations, confirmItem, rejectItem, ignoreItem } from '@/services/hrConfirmationService'
import type { ConfirmationItem } from '@/types/hr-confirmation'
import { formatDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import BaseSkeleton from '@/components/base/BaseSkeleton.vue'
import { Check, X, EyeOff, ArrowLeft, AlertCircle, CreditCard, User } from 'lucide-vue-next'

const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const items = ref<ConfirmationItem[]>([])
const loading = ref(true)
const total = ref(0)
const pendingCount = ref(0)
const page = ref(1)
const pageSize = 20
const activeFilter = ref<string>('')

interface ConfirmMeta {
  itemId: number
  action: 'confirm' | 'reject' | 'ignore'
  title?: string
}

const confirmMeta = ref<ConfirmMeta | null>(null)

const statusMap: Record<string, { label: string; color: string }> = {
  PENDING: { label: '待确认', color: 'warning' },
  CONFIRMED: { label: '已确认', color: 'success' },
  REJECTED: { label: '已拒绝', color: 'danger' },
  IGNORED: { label: '已忽略', color: 'default' },
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (activeFilter.value) params.status = activeFilter.value
    const result = await listConfirmations(params)
    items.value = result.items
    total.value = result.total
    pendingCount.value = result.pending_count
  } catch (e: any) {
    showToast({ message: '加载失败: ' + (e.message || '未知错误'), type: 'error' })
  } finally {
    loading.value = false
  }
}

function doConfirm(item: ConfirmationItem) {
  confirmMeta.value = { itemId: item.id, action: 'confirm', title: item.title }
  confirm({
    title: '确认操作',
    message: `确认「${item.title}」？确认后将执行对应的业务操作。`,
    confirmText: '确认',
    onConfirm: async () => {
      try {
        if (!confirmMeta.value) return
        await confirmItem(confirmMeta.value.itemId)
        showToast({ message: '已确认', type: 'success' })
        confirmMeta.value = null
        await loadData()
      } catch (e: any) {
        showToast({ message: '确认失败: ' + (e.message || '未知错误'), type: 'error' })
      }
    },
  })
}

function doReject(item: ConfirmationItem) {
  confirmMeta.value = { itemId: item.id, action: 'reject', title: item.title }
  confirm({
    title: '拒绝操作',
    message: `拒绝「${item.title}」？拒绝后不会修改业务数据。`,
    confirmText: '拒绝',
    danger: true,
    onConfirm: async () => {
      try {
        if (!confirmMeta.value) return
        await rejectItem(confirmMeta.value.itemId)
        showToast({ message: '已拒绝', type: 'success' })
        confirmMeta.value = null
        await loadData()
      } catch (e: any) {
        showToast({ message: '操作失败: ' + (e.message || '未知错误'), type: 'error' })
      }
    },
  })
}

function doIgnore(item: ConfirmationItem) {
  confirmMeta.value = { itemId: item.id, action: 'ignore', title: item.title }
  confirm({
    title: '忽略操作',
    message: `忽略「${item.title}」？忽略后提醒消失，不修改业务数据。`,
    confirmText: '忽略',
    onConfirm: async () => {
      try {
        if (!confirmMeta.value) return
        await ignoreItem(confirmMeta.value.itemId)
        showToast({ message: '已忽略', type: 'success' })
        confirmMeta.value = null
        await loadData()
      } catch (e: any) {
        showToast({ message: '操作失败: ' + (e.message || '未知错误'), type: 'error' })
      }
    },
  })
}

function setFilter(status: string) {
  activeFilter.value = status
  page.value = 1
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="confirmation-page">
    <div class="page-header">
      <button class="back-btn" @click="router.push('/dashboard')">
        <ArrowLeft :size="18" />
      </button>
      <h2>待确认事项</h2>
      <span v-if="pendingCount > 0" class="pending-badge">{{ pendingCount }} 条待处理</span>
    </div>

    <!-- 筛选 -->
    <div class="filter-tabs">
      <button :class="{ active: activeFilter === '' }" @click="setFilter('')">全部 ({{ total }})</button>
      <button :class="{ active: activeFilter === 'PENDING' }" @click="setFilter('PENDING')">待处理 ({{ pendingCount }})</button>
      <button :class="{ active: activeFilter === 'CONFIRMED' }" @click="setFilter('CONFIRMED')">已确认</button>
      <button :class="{ active: activeFilter === 'REJECTED' }" @click="setFilter('REJECTED')">已拒绝</button>
      <button :class="{ active: activeFilter === 'IGNORED' }" @click="setFilter('IGNORED')">已忽略</button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="loading-section">
      <BaseSkeleton :rows="5" type="table" />
    </div>

    <!-- 空数据 -->
    <BaseEmpty v-else-if="items.length === 0" message="暂无待确认事项" />

    <!-- 列表 -->
    <div v-else class="confirmation-list">
      <div v-for="item in items" :key="item.id" class="confirmation-card" :class="{ 'is-pending': item.item_status === 'PENDING' }">
        <div class="card-icon">
          <AlertCircle v-if="item.issue_code.includes('CONTRACT') || item.issue_code.includes('SEPARATION')" :size="20" class="icon-warning" />
          <CreditCard v-else-if="item.issue_code.includes('BANK') || item.issue_code.includes('ACCOUNT')" :size="20" class="icon-info" />
          <User v-else :size="20" class="icon-info" />
        </div>
        <div class="card-body">
          <div class="card-title-row">
            <span class="card-title">{{ item.title }}</span>
            <BaseBadge :variant="statusMap[item.item_status]?.color || 'default'">
              {{ statusMap[item.item_status]?.label || item.item_status }}
            </BaseBadge>
          </div>
          <div v-if="item.description" class="card-desc">{{ item.description }}</div>
          <div class="card-meta">
            <span v-if="item.employee_name" class="meta-employee">{{ item.employee_name }}</span>
            <span class="meta-time">创建于 {{ formatDate(item.created_at) }}</span>
          </div>
          <div v-if="item.before_data || item.after_data" class="card-diff">
            <div v-if="item.before_data" class="diff-item diff-old">
              <span class="diff-label">原值:</span>
              <span class="diff-value">{{ String(item.before_data) }}</span>
            </div>
            <div v-if="item.after_data" class="diff-item diff-new">
              <span class="diff-label">新值:</span>
              <span class="diff-value">{{ String(item.after_data) }}</span>
            </div>
          </div>
          <div v-if="item.item_status === 'PENDING'" class="card-actions">
            <button class="action-btn action-confirm" @click="doConfirm(item)">
              <Check :size="16" /> 确认
            </button>
            <button class="action-btn action-reject" @click="doReject(item)">
              <X :size="16" /> 拒绝
            </button>
            <button class="action-btn action-ignore" @click="doIgnore(item)">
              <EyeOff :size="16" /> 忽略
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm Modal -->
    <BaseModal v-if="showConfirm" :title="confirmOpts.title || '确认'" @confirm="handleConfirm" @cancel="handleCancel">
      <p>{{ confirmOpts.message }}</p>
    </BaseModal>
  </div>
</template>

<style scoped>
.confirmation-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  background: var(--color-bg, #f5f5f5);
  cursor: pointer;
  color: var(--color-text-secondary);
}
.back-btn:hover {
  background: var(--color-border, #e0e0e0);
}
.pending-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: #fff;
  background: var(--color-danger, #e53e3e);
}
.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filter-tabs button {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.filter-tabs button.active {
  background: var(--color-primary, #4F46E5);
  color: #fff;
  border-color: var(--color-primary);
}
.filter-tabs button:hover:not(.active) {
  background: var(--color-bg, #f5f5f5);
}
.loading-section {
  padding: 24px 0;
}
.confirmation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.confirmation-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface, #fff);
}
.confirmation-card.is-pending {
  border-left: 3px solid var(--color-primary, #4F46E5);
}
.card-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--color-bg, #f5f5f5);
}
.icon-warning { color: var(--color-warning, #d69e2e); }
.icon-info { color: var(--color-primary, #4F46E5); }
.card-body {
  flex: 1;
  min-width: 0;
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.card-title {
  font-weight: 500;
  font-size: 14px;
}
.card-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-bottom: 8px;
}
.card-diff {
  background: var(--color-bg, #f9f9f9);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 10px;
  font-size: 12px;
}
.diff-item {
  display: flex;
  gap: 8px;
  margin-bottom: 2px;
}
.diff-label {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.diff-value {
  word-break: break-all;
  color: var(--color-text-secondary);
}
.card-actions {
  display: flex;
  gap: 8px;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.action-btn:hover {
  background: var(--color-bg, #f5f5f5);
}
.action-confirm {
  color: var(--color-success, #38a169);
  border-color: var(--color-success);
}
.action-confirm:hover {
  background: #f0fff4;
}
.action-reject {
  color: var(--color-danger, #e53e3e);
  border-color: var(--color-danger);
}
.action-reject:hover {
  background: #fff5f5;
}
.action-ignore {
  color: var(--color-text-tertiary);
}
</style>
