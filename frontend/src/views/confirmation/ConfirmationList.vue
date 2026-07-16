<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listConfirmations, confirmItem, rejectItem, ignoreItem } from '@/services/hrConfirmationService'
import type { ConfirmationItem } from '@/types/hr-confirmation'
import { formatDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import BaseSkeleton from '@/components/base/BaseSkeleton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { Check, X, EyeOff, AlertCircle, CreditCard, User, Calendar } from 'lucide-vue-next'

const route = useRoute()
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

// 需要填写数据的确认事项类型
const DATA_REQUIRING_ISSUE_CODES: Record<string, { fields: Array<{ key: string; label: string; type: string }> }> = {
  MISSING_HIRE_DATE: {
    fields: [
      { key: 'hire_date', label: '实际入职日期', type: 'date' },
    ],
  },
  MISSING_REGULARIZATION_DATE: {
    fields: [
      { key: 'actual_regularization_date', label: '实际转正日期', type: 'date' },
    ],
  },
}

// 当前确认操作的状态
const currentActionItem = ref<ConfirmationItem | null>(null)
const actionData = ref<Record<string, string>>({})
const actionSubmitting = ref(false)
const showActionForm = ref(false)

const statusMap: Record<string, { label: string; color: string }> = {
  PENDING: { label: '待确认', color: 'warning' },
  CONFIRMED: { label: '已确认', color: 'success' },
  REJECTED: { label: '已拒绝', color: 'danger' },
  IGNORED: { label: '已忽略', color: 'default' },
}

function isDataRequired(code: string): boolean {
  return code in DATA_REQUIRING_ISSUE_CODES
}

function getRequiredFields(code: string): Array<{ key: string; label: string; type: string }> {
  return DATA_REQUIRING_ISSUE_CODES[code]?.fields || []
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (activeFilter.value) params.status = activeFilter.value
    // 支持路由传入的筛选
    if (route.query.batch_id) params.import_batch_id = Number(route.query.batch_id)
    if (route.query.import_row_id) params.import_row_id = Number(route.query.import_row_id)
    if (route.query.issue_code) params.issue_code = route.query.issue_code
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

// 打开确认表单（对需要填写数据的类型，显示表单）
function openConfirmForm(item: ConfirmationItem) {
  currentActionItem.value = item
  if (isDataRequired(item.issue_code)) {
    actionData.value = {}
    showActionForm.value = true
  } else {
    // 不需要数据，直接确认
    doSimpleConfirm(item)
  }
}

function closeActionForm() {
  showActionForm.value = false
  currentActionItem.value = null
  actionData.value = {}
}

async function submitActionForm() {
  if (!currentActionItem.value) return
  actionSubmitting.value = true
  try {
    await confirmItem(currentActionItem.value.id, undefined, actionData.value)
    showToast({ message: '已确认', type: 'success' })
    closeActionForm()
    await loadData()
  } catch (e: any) {
    showToast({ message: '确认失败: ' + (e.message || '未知错误'), type: 'error' })
  } finally {
    actionSubmitting.value = false
  }
}

function doSimpleConfirm(item: ConfirmationItem) {
  confirm({
    title: '确认操作',
    message: `确认「${item.title}」？确认后将执行对应的业务操作。`,
    confirmText: '确认',
    onConfirm: async () => {
      try {
        await confirmItem(item.id)
        showToast({ message: '已确认', type: 'success' })
        await loadData()
      } catch (e: any) {
        showToast({ message: '确认失败: ' + (e.message || '未知错误'), type: 'error' })
      }
    },
  })
}

function doReject(item: ConfirmationItem) {
  confirm({
    title: '拒绝操作',
    message: `拒绝「${item.title}」？拒绝后不会修改业务数据。`,
    confirmText: '拒绝',
    danger: true,
    onConfirm: async () => {
      try {
        await rejectItem(item.id)
        showToast({ message: '已拒绝', type: 'success' })
        await loadData()
      } catch (e: any) {
        showToast({ message: '操作失败: ' + (e.message || '未知错误'), type: 'error' })
      }
    },
  })
}

function doIgnore(item: ConfirmationItem) {
  confirm({
    title: '忽略操作',
    message: `忽略「${item.title}」？忽略后提醒消失，不修改业务数据。`,
    confirmText: '忽略',
    onConfirm: async () => {
      try {
        await ignoreItem(item.id)
        showToast({ message: '已忽略', type: 'success' })
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
    <PageHeader title="待确认事项" :subtitle="pendingCount > 0 ? `${pendingCount} 条待处理` : '查看需要确认的业务操作'" />

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
            <button class="action-btn action-confirm" @click="openConfirmForm(item)">
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

    <!-- Action Form Modal (for issues that need data input) -->
    <BaseModal
      v-if="showActionForm && currentActionItem"
      :show="showActionForm"
      :title="'填写信息 - ' + (currentActionItem.title || '')"
      @confirm="submitActionForm"
      @cancel="closeActionForm"
    >
      <template #message>
        <div class="action-form">
          <p class="form-desc">{{ currentActionItem.description }}</p>
          <div v-for="field in getRequiredFields(currentActionItem.issue_code)" :key="field.key" class="form-field">
            <label :for="'field-' + field.key">{{ field.label }}</label>
            <input
              :id="'field-' + field.key"
              v-model="actionData[field.key]"
              :type="field.type"
              class="form-input"
              :required="true"
            />
          </div>
        </div>
      </template>
      <template #actions>
        <BaseButton variant="secondary" @click="closeActionForm">取消</BaseButton>
        <BaseButton variant="primary" :loading="actionSubmitting" @click="submitActionForm">
          <Check :size="16" /> 确认
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.confirmation-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
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
/* Action form modal styles */
.action-form {
  padding: 8px 0;
}
.form-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}
.form-field {
  margin-bottom: 14px;
}
.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}
.form-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--color-surface);
  color: var(--color-text-primary);
}
.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
}
</style>
