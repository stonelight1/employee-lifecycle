<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch, del as delReq } from '@/api'
import type { EmployeeItem, EmploymentItem } from '@/types'
import { formatDate, formatTenure } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import EmployeeAvatar from '@/components/business/EmployeeAvatar.vue'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import LifecycleStepper from '@/components/business/LifecycleStepper.vue'
import NextActionCard from '@/components/business/NextActionCard.vue'
import EmployeeTimeline from '@/components/business/EmployeeTimeline.vue'
import ProbationProgress from '@/components/business/ProbationProgress.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const employeeId = Number(route.params.id)
const employee = ref<EmployeeItem | null>(null)
const employments = ref<EmploymentItem[]>([])
const currentEmployment = ref<EmploymentItem | null>(null)
const loading = ref(true)
const activeTab = ref('overview')

function resolveLifecycleStatus(employment?: EmploymentItem | null, fallbackStatus?: string) {
  if (!employment) return fallbackStatus
  if (employment.employment_status === 'PENDING') return 'PENDING'
  if (employment.employment_status === 'SEPARATING') return 'SEPARATING'
  if (employment.employment_status === 'SEPARATED') return 'SEPARATED'
  if (['NOT_STARTED', 'IN_PROGRESS', 'PENDING_REVIEW'].includes(employment.probation_status)) {
    return 'PROBATION'
  }
  return 'ACTIVE'
}

function isInProbation(employment?: EmploymentItem | null) {
  return resolveLifecycleStatus(employment) === 'PROBATION'
}

function pickCurrentEmployment(items: EmploymentItem[]) {
  return items.find((item) => ['PENDING', 'ACTIVE', 'SEPARATING'].includes(item.employment_status)) || items[0] || null
}

async function loadData() {
  loading.value = true
  try {
    const empRes = await get<EmployeeItem>(`/employees/${employeeId}`)
    if (empRes.success) employee.value = empRes.data!

    const empListRes = await get<{ items: EmploymentItem[]; total: number }>(`/employees/${employeeId}/employments`)
    if (empListRes.data?.items) {
      employments.value = empListRes.data.items
      currentEmployment.value = pickCurrentEmployment(empListRes.data.items)
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const lifecycleSteps = computed(() => {
  const status = resolveLifecycleStatus(currentEmployment.value, employee.value?.employee_status)
  return [
    { key: 'PENDING', label: '待入职', completed: false, current: status === 'PENDING' },
    { key: 'PROBATION', label: '试用期', completed: status !== 'PROBATION' && status !== 'PENDING', current: status === 'PROBATION' },
    { key: 'REGULARIZATION_PENDING', label: '待转正', completed: false, current: status === 'REGULARIZATION_PENDING' },
    { key: 'ACTIVE', label: '正式在职', completed: status === 'SEPARATED' || status === 'SEPARATING', current: status === 'ACTIVE' },
    { key: 'SEPARATED', label: '离职', completed: false, current: status === 'SEPARATED' || status === 'SEPARATING' },
  ]
})

const actionsList = computed(() => {
  const status = currentEmployment.value?.employment_status
  const actions: { label: string; handler: () => void }[] = []

  if (isInProbation(currentEmployment.value)) {
    actions.push(
      { label: '记录沟通', handler: () => {} },
      { label: '新增评估', handler: () => router.push(`/employments/${currentEmployment.value?.id}/probation-reviews/create`) },
      { label: '发起转正', handler: () => router.push(`/employments/${currentEmployment.value?.id}/regularization`) },
      { label: '启动离职', handler: () => router.push(`/employments/${currentEmployment.value?.id}/separation`) },
    )
  } else if (status === 'ACTIVE') {
    actions.push(
      { label: '记录沟通', handler: () => {} },
      { label: '发起异动', handler: () => router.push(`/employments/${currentEmployment.value?.id}/changes/create`) },
      { label: '启动离职', handler: () => router.push(`/employments/${currentEmployment.value?.id}/separation`) },
    )
  } else if (status === 'SEPARATED') {
    actions.push(
      { label: '查看离职记录', handler: () => router.push(`/employments/${currentEmployment.value?.id}/separation`) },
    )
  }

  return actions
})

function handleDelete() {
  confirm({
    title: '确认删除员工',
    message: `确定要永久删除员工「${employee.value?.name}」？此操作不可恢复。`,
    confirmText: '确认删除',
    danger: true,
    onConfirm: async () => {
      try {
        await delReq(`/employees/${employeeId}`)
        showToast({ message: '员工已删除', type: 'success' })
        router.push('/employees')
      } catch (e: any) {
        showToast({ message: e.message || '删除失败', type: 'error' })
      }
    },
  })
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <!-- Loading -->
    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <!-- Employee detail -->
    <template v-if="employee">
      <!-- Back link -->
      <button class="back-link" @click="router.push('/employees')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        返回员工中心
      </button>

      <!-- Identity card -->
      <div class="identity-card card">
        <div class="identity-bar">
          <EmployeeAvatar :name="employee.name" size="lg" />
          <div class="identity-info">
            <div class="identity-top">
              <h1 class="identity-name">{{ employee.name }}</h1>
              <LifecycleBadge :status="resolveLifecycleStatus(currentEmployment, employee.employee_status)" />
            </div>
            <div class="identity-meta">
              <span>{{ currentEmployment?.department || '—' }}</span>
              <span class="meta-dot">·</span>
              <span>{{ currentEmployment?.position || '—' }}</span>
              <span class="meta-dot">·</span>
              <span>{{ formatDate(currentEmployment?.hire_date) }} 入职</span>
            </div>
            <div class="identity-next">
              <NextActionCard
                title="7 天跟进已逾期 2 天"
                description="建议尽快完成沟通并记录结果"
                action-label="立即处理"
                :overdue="2"
              />
            </div>
          </div>
          <div class="identity-actions">
            <button class="action-icon-btn" :title="action.label" v-for="action in actionsList" :key="action.label" @click="action.handler">
              {{ action.label }}
            </button>
            <button class="action-icon-btn danger" @click="handleDelete">删除</button>
          </div>
        </div>

        <!-- Lifecycle stepper -->
        <div class="stepper-section">
          <LifecycleStepper :steps="lifecycleSteps" />
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">概览</button>
        <button class="tab-btn" :class="{ active: activeTab === 'employment' }" @click="activeTab = 'employment'">任职经历</button>
        <button class="tab-btn" :class="{ active: activeTab === 'probation' }" @click="activeTab = 'probation'" v-if="isInProbation(currentEmployment)">跟进与评估</button>
        <button class="tab-btn" :class="{ active: activeTab === 'changes' }" @click="activeTab = 'changes'">异动与离职</button>
      </div>

      <!-- Overview tab -->
      <div v-if="activeTab === 'overview'" class="detail-columns">
        <div class="col-left">
          <div class="card section-card">
            <div class="section-title">基本信息</div>
            <div class="info-grid">
              <div class="info-item"><label>员工编号</label><span>{{ employee.employee_no || '—' }}</span></div>
              <div class="info-item"><label>姓名</label><span>{{ employee.name }}</span></div>
              <div class="info-item"><label>手机号</label><span>{{ employee.mobile || '—' }}</span></div>
              <div class="info-item"><label>邮箱</label><span>{{ employee.email || '—' }}</span></div>
              <div class="info-item"><label>来源</label><span>{{ employee.source || '—' }}</span></div>
              <div class="info-item"><label>创建时间</label><span>{{ formatDate(employee.created_at) }}</span></div>
            </div>
          </div>

          <div class="card section-card">
            <div class="section-title">员工时间线</div>
            <EmployeeTimeline :events="[]" />
          </div>
        </div>

        <div class="col-right">
          <div class="card section-card">
            <div class="section-title">当前任职</div>
            <div v-if="currentEmployment" class="info-grid">
              <div class="info-item"><label>部门</label><span>{{ currentEmployment.department || '—' }}</span></div>
              <div class="info-item"><label>岗位</label><span>{{ currentEmployment.position || '—' }}</span></div>
              <div class="info-item"><label>入职日期</label><span>{{ formatDate(currentEmployment.hire_date) }}</span></div>
              <div class="info-item"><label>在职时长</label><span>{{ formatTenure(currentEmployment.hire_date) }}</span></div>
            </div>
            <div v-else class="text-tertiary text-sm">暂无任职记录</div>
          </div>

          <div v-if="isInProbation(currentEmployment)" class="card section-card">
            <div class="section-title">试用期进度</div>
            <ProbationProgress
              :hire-date="currentEmployment?.hire_date"
              :probation-end-date="currentEmployment?.probation_end_date"
              size="md"
            />
          </div>
        </div>
      </div>

      <!-- Employment tab -->
      <div v-if="activeTab === 'employment'" class="card section-card">
        <div class="flex justify-between items-center mb-4">
          <div class="section-title" style="border: none; margin: 0; padding: 0;">任职记录</div>
          <button class="btn-primary-sm" @click="router.push(`/employees/${employeeId}/employments/new`)">新增任职</button>
        </div>
        <div v-if="employments.length === 0" class="text-tertiary text-sm text-center py-4">暂无任职记录</div>
        <div v-for="emp in employments" :key="emp.id" class="employment-row">
          <div class="employment-info">
            <div><strong>{{ emp.department || '—' }}</strong> · {{ emp.position || '—' }}</div>
            <div class="text-xs text-tertiary mt-1">入职 {{ formatDate(emp.hire_date) }}</div>
          </div>
          <div class="emp-status-badge">
            <LifecycleBadge :status="resolveLifecycleStatus(emp)" size="sm" />
          </div>
          <div class="emp-row-links">
            <router-link :to="`/employees/${employeeId}/employments/${emp.id}`" class="text-sm">详情</router-link>
            <router-link :to="`/employments/${emp.id}/probation-reviews`" class="text-sm">评估</router-link>
            <router-link :to="`/employments/${emp.id}/regularization`" class="text-sm">转正</router-link>
            <router-link :to="`/employments/${emp.id}/changes`" class="text-sm">异动</router-link>
            <router-link :to="`/employments/${emp.id}/separation`" class="text-sm">离职</router-link>
          </div>
        </div>
      </div>

      <!-- Probation tab -->
      <div v-if="activeTab === 'probation'" class="card section-card">
        <div class="section-title">跟进与评估</div>
        <div class="text-sm text-tertiary">
          <router-link :to="`/employments/${currentEmployment?.id}/probation-reviews`" class="text-primary">查看试用期评估</router-link>
        </div>
      </div>

      <!-- Changes tab -->
      <div v-if="activeTab === 'changes'" class="card section-card">
        <div class="section-title">异动与离职</div>
        <div class="flex gap-4">
          <router-link v-if="currentEmployment?.id" :to="`/employments/${currentEmployment.id}/changes`" class="text-sm text-primary">查看异动记录</router-link>
          <router-link v-if="currentEmployment?.id" :to="`/employments/${currentEmployment.id}/separation`" class="text-sm text-primary">查看离职记录</router-link>
        </div>
      </div>
    </template>

    <!-- Delete confirm -->
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
.page {
  max-width: 1400px;
}

/* Back */
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  margin-bottom: 16px;
  padding: 4px 0;
}
.back-link:hover {
  color: var(--color-primary);
}

/* Identity card */
.identity-card {
  padding: 24px;
  margin-bottom: 20px;
}
.identity-bar {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.identity-info {
  flex: 1;
}
.identity-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.identity-name {
  font-size: 24px;
  font-weight: 700;
}
.identity-meta {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.meta-dot {
  color: var(--color-text-tertiary);
  margin: 0 4px;
}
.identity-next {
  margin-top: 16px;
}
.identity-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}
.action-icon-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: var(--font-size-sm);
  cursor: pointer;
  white-space: nowrap;
}
.action-icon-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.action-icon-btn.danger {
  color: var(--color-danger);
}
.action-icon-btn.danger:hover {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.stepper-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

/* Tabs */
.tabs-bar {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-bottom: 2px solid var(--color-border);
}
.tab-btn {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn:hover {
  color: var(--color-text-primary);
}
.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 500;
}

/* Detail columns */
.detail-columns {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 16px;
  align-items: start;
}
.section-card {
  padding: 20px;
  margin-bottom: 16px;
}

.employment-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}
.employment-row:last-child {
  border-bottom: none;
}
.employment-info {
  flex: 1;
}
.emp-row-links {
  display: flex;
  gap: 12px;
}
.emp-row-links a {
  color: var(--color-primary);
  font-size: var(--font-size-sm);
}

.btn-primary-sm {
  padding: 6px 14px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}

@media (max-width: 1024px) {
  .detail-columns {
    grid-template-columns: 1fr;
  }
}
</style>
