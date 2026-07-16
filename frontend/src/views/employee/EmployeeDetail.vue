<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch, del as delReq } from '@/api'
import type { EmployeeItem, EmploymentItem } from '@/types'
import type { FullProfile } from '@/types/employee-profile'
import { formatDate, formatTenure, formatDateTime } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { resolveLifecycleStage, isInProbation, pickCurrentEmployment } from '@/utils/lifecycle'
import {
  getStatusLabel,
  employeeStatusMap,
  probationStatusMap,
  employmentStatusMap,
  contractTypeMap,
  contractStatusMap,
  accountTypeMap,
  accountStatusMap,
  salaryTypeMap,
  assessmentTypeMap,
  genderMap,
  householdTypeMap,
  educationLevelMap,
  workModeMap,
  employmentTypeMap,
  socialInsuranceStatusMap,
  housingFundStatusMap,
  benefitPolicyMap,
} from '@/constants/status'
import EmployeeAvatar from '@/components/business/EmployeeAvatar.vue'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import LifecycleStepper from '@/components/business/LifecycleStepper.vue'
import NextActionCard from '@/components/business/NextActionCard.vue'
import EmployeeTimeline from '@/components/business/EmployeeTimeline.vue'
import ProbationProgress from '@/components/business/ProbationProgress.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import {
  User,
  MapPin,
  GraduationCap,
  Briefcase,
  FileText,
  Banknote,
  CreditCard,
  Shield,
  Brain,
  StickyNote,
  History,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const employeeId = Number(route.params.id)
const employee = ref<EmployeeItem | null>(null)
const employments = ref<EmploymentItem[]>([])
const currentEmployment = ref<EmploymentItem | null>(null)
const timelineEvents = ref<any[]>([])
const timelineTotal = ref(0)
const timelineError = ref('')
const timelineLoading = ref(false)
const loading = ref(true)
const activeTab = ref('overview')

const fullProfile = ref<FullProfile | null>(null)
const fullProfileLoading = ref(false)
const fullProfileError = ref('')

async function loadData() {
  loading.value = true
  try {
    const [empRes, empListRes] = await Promise.all([
      get<EmployeeItem>(`/employees/${employeeId}`),
      get<{ items: EmploymentItem[]; total: number }>(`/employees/${employeeId}/employments`),
    ])

    if (empRes.success) employee.value = empRes.data!

    if (empListRes.data?.items) {
      employments.value = empListRes.data.items
      currentEmployment.value = pickCurrentEmployment(empListRes.data.items)
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
  void loadTimeline()
}

async function loadTimeline(limit = 10) {
  timelineLoading.value = true
  timelineError.value = ''
  try {
    const res = await get<any>(`/employees/${employeeId}/timeline`, { limit })
    if (res.success && res.data) {
      if (Array.isArray(res.data)) {
        timelineEvents.value = res.data
        timelineTotal.value = res.data.length
      } else {
        timelineEvents.value = res.data.items || []
        timelineTotal.value = res.data.total || 0
      }
    } else {
      timelineError.value = '时间线加载失败'
    }
  } catch {
    timelineError.value = '时间线加载失败'
  } finally {
    timelineLoading.value = false
  }
}

function loadMoreTimeline() {
  const nextLimit = Math.min(Math.max(timelineEvents.value.length + 10, 10), 100)
  void loadTimeline(nextLimit)
}

const lifecycleStatus = computed(() =>
  resolveLifecycleStage(currentEmployment.value, employee.value?.employee_status),
)

const lifecycleSteps = computed(() => {
  const status = lifecycleStatus.value
  return [
    { key: 'PENDING', label: '待入职', completed: false, current: status === 'PENDING' },
    { key: 'PROBATION', label: '试用期', completed: status !== 'PROBATION' && status !== 'PENDING' && status !== 'UNKNOWN', current: status === 'PROBATION' },
    { key: 'REGULARIZATION_PENDING', label: '待转正', completed: false, current: status === 'REGULARIZATION_PENDING' },
    { key: 'ACTIVE', label: '正式在职', completed: status === 'SEPARATED' || status === 'SEPARATING', current: status === 'ACTIVE' },
    { key: 'SEPARATED', label: '离职', completed: false, current: status === 'SEPARATED' || status === 'SEPARATING' },
  ]
})

const actionsList = computed(() => {
  const status = currentEmployment.value?.employment_status
  const employmentId = currentEmployment.value?.id
  const lifecycleStage = lifecycleStatus.value
  const actions: { label: string; handler: () => void }[] = []

  if (lifecycleStage === 'PENDING') {
    // 待入职：只显示真实可用的操作
    return [
      {
        label: '编辑员工',
        handler: () => router.push(`/employees/${employeeId}/edit`),
      },
    ]
  }

  if (isInProbation(currentEmployment.value)) {
    actions.push(
      {
        label: '记录沟通',
        handler: () => {
          if (employmentId) {
            router.push(`/communications/create?employment_id=${employmentId}&employee_id=${employeeId}`)
          }
        },
      },
      { label: '新增评估', handler: () => router.push(`/employments/${employmentId}/probation-reviews/create`) },
      { label: '发起转正', handler: () => router.push(`/employments/${employmentId}/regularization`) },
      { label: '启动离职', handler: () => router.push(`/employments/${employmentId}/separation`) },
    )
  } else if (status === 'ACTIVE') {
    actions.push(
      { label: '记录沟通', handler: () => router.push(`/communications/create?employment_id=${employmentId}&employee_id=${employeeId}`) },
      { label: '发起异动', handler: () => router.push(`/employments/${employmentId}/changes/create`) },
      { label: '启动离职', handler: () => router.push(`/employments/${employmentId}/separation`) },
    )
  } else if (status === 'SEPARATED') {
    actions.push(
      { label: '查看离职记录', handler: () => router.push(`/employments/${employmentId}/separation`) },
    )
  }

  return actions
})

// 计算下一步行动来自真实数据
const nextActionInfo = computed(() => {
  const emp = currentEmployment.value
  if (!emp) return null

  const today = new Date()
  const todayStr = today.toISOString().slice(0, 10)

  // 待入职状态
  if (lifecycleStatus.value === 'PENDING') {
    return null
  }

  // 检查跟进任务
  if (emp.probation_status === 'PENDING_REVIEW') {
    return {
      title: '待转正审批',
      description: `预计转正日期 ${formatDate(emp.probation_end_date)}`,
      actionLabel: '处理转正',
      handler: () => router.push(`/employments/${emp.id}/regularization`),
    }
  }
  if (emp.probation_status === 'IN_PROGRESS' && emp.probation_end_date && emp.probation_end_date < todayStr) {
    return {
      title: '试用期已超期',
      description: `预计转正日期 ${formatDate(emp.probation_end_date)}，已超期`,
      actionLabel: '处理转正',
      handler: () => router.push(`/employments/${emp.id}/regularization`),
    }
  }
  if (emp.employment_status === 'PENDING') {
    return {
      title: '待入职',
      description: `入职日期 ${formatDate(emp.hire_date)}`,
      actionLabel: '查看任职',
      handler: () => router.push(`/employees/${employeeId}/employments/${emp.id}`),
    }
  }
  if (emp.employment_status === 'SEPARATING') {
    return {
      title: '离职办理中',
      description: '该员工正在进行离职流程',
      actionLabel: '查看离职',
      handler: () => router.push(`/employments/${emp.id}/separation`),
    }
  }

  // 获取跟进任务数据
  return null
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

function maskAccountNo(value?: string | null): string {
  if (!value) return '—'
  if (value.length <= 4) return value
  return '****' + value.slice(-4)
}

const emp = computed(() => fullProfile.value?.current_employment as Record<string, any> | null | undefined)
const profile = computed(() => fullProfile.value?.profile ?? null)

async function loadFullProfile() {
  fullProfileLoading.value = true
  fullProfileError.value = ''
  try {
    const res = await get<FullProfile>(`/employees/${employeeId}/full-profile`)
    if (res.success && res.data) {
      fullProfile.value = res.data
    } else {
      fullProfileError.value = '完整资料加载失败'
    }
  } catch {
    // Fallback: load individual endpoints
    try {
      const [profileRes, contractsRes, accountsRes, compensationsRes, assessmentsRes, notesRes, historyRes] =
        await Promise.all([
          get<any>(`/employees/${employeeId}/profile`).catch(() => ({ data: null })),
          get<any>(`/employees/${employeeId}/contracts`).catch(() => ({ data: [] })),
          get<any>(`/employees/${employeeId}/financial-accounts`).catch(() => ({ data: [] })),
          get<any>(`/employees/${employeeId}/compensations`).catch(() => ({ data: [] })),
          get<any>(`/employees/${employeeId}/assessments`).catch(() => ({ data: [] })),
          get<any>(`/employees/${employeeId}/notes`).catch(() => ({ data: [] })),
          get<any>(`/employees/${employeeId}/attribute-history`).catch(() => ({ data: [] })),
        ])

      fullProfile.value = {
        employee: employee.value as any,
        profile: profileRes.data?.profile ?? null,
        current_employment: currentEmployment.value as any,
        all_employments: employments.value as any,
        contracts: contractsRes.data?.items ?? contractsRes.data ?? [],
        financial_accounts: accountsRes.data?.items ?? accountsRes.data ?? [],
        compensations: compensationsRes.data?.items ?? compensationsRes.data ?? [],
        assessments: assessmentsRes.data?.items ?? assessmentsRes.data ?? [],
        notes: notesRes.data?.items ?? notesRes.data ?? [],
        attribute_history: historyRes.data?.items ?? historyRes.data ?? [],
      }
      fullProfileError.value = ''
    } catch (e2) {
      fullProfileError.value = '资料加载失败'
    }
  } finally {
    fullProfileLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'full-profile' && !fullProfile.value && !fullProfileLoading.value) {
    void loadFullProfile()
  }
})

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
              <LifecycleBadge :status="lifecycleStatus" />
            </div>
            <div class="identity-meta">
              <span>{{ currentEmployment?.department || '—' }}</span>
              <span class="meta-dot">·</span>
              <span>{{ currentEmployment?.position || '—' }}</span>
              <span class="meta-dot">·</span>
              <span>{{ formatDate(currentEmployment?.hire_date) }} 入职</span>
            </div>
            <div v-if="lifecycleStatus === 'PENDING'" class="identity-next">
              <div class="card pending-info-card">
                <p class="text-sm text-tertiary">员工尚未入职</p>
                <p class="text-xs text-tertiary" style="margin-top:4px;">入职后系统会自动生成试用期和跟进节点</p>
              </div>
            </div>
            <div v-else-if="nextActionInfo" class="identity-next">
              <NextActionCard
                :title="nextActionInfo.title"
                :description="nextActionInfo.description"
                :action-label="nextActionInfo.actionLabel"
                @action="nextActionInfo.handler"
              />
            </div>
            <div v-else class="identity-next">
              <p class="text-sm text-tertiary">当前暂无需要处理的事项</p>
            </div>
          </div>
          <div class="identity-actions">
            <button
              v-for="action in actionsList"
              :key="action.label"
              class="action-icon-btn"
              :title="action.label"
              @click="action.handler"
            >
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
        <button class="tab-btn" :class="{ active: activeTab === 'full-profile' }" @click="activeTab = 'full-profile'">完整资料</button>
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
            <EmployeeTimeline
              :events="timelineEvents"
              :total="timelineTotal"
              :loading="timelineLoading"
              :error="timelineError"
              @retry="loadTimeline"
              @load-more="loadMoreTimeline"
            />
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

          <div v-if="nextActionInfo" class="card section-card">
            <div class="section-title">下一步行动</div>
            <NextActionCard
              :title="nextActionInfo.title"
              :description="nextActionInfo.description"
              :action-label="nextActionInfo.actionLabel"
              @action="nextActionInfo.handler"
            />
          </div>
        </div>
      </div>

      <!-- Full Profile tab -->
      <div v-if="activeTab === 'full-profile'" class="full-profile">
        <div v-if="fullProfileLoading" class="loading-state text-tertiary">加载中...</div>
        <div v-else-if="fullProfileError" class="error-state text-danger">{{ fullProfileError }}</div>
        <template v-else-if="fullProfile">
          <!-- 1. 基本信息 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <User :size="16" />
              <span>基本信息</span>
            </div>
            <div class="profile-grid">
              <div class="profile-field"><label>姓名</label><span>{{ employee.name }}</span></div>
              <div class="profile-field"><label>员工编号</label><span>{{ employee.employee_no || '—' }}</span></div>
              <div class="profile-field"><label>员工状态</label><span><LifecycleBadge :status="lifecycleStatus" /></span></div>
              <div class="profile-field"><label>来源</label><span>{{ employee.source || '—' }}</span></div>
            </div>
          </div>

          <!-- 2. 身份与联系方式 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <User :size="16" />
              <span>身份与联系方式</span>
            </div>
            <div class="profile-grid">
              <div class="profile-field"><label>手机号</label><span>{{ employee.mobile || '—' }}</span></div>
              <div class="profile-field"><label>邮箱</label><span>{{ employee.email || '—' }}</span></div>
              <!-- 身份证号直接展示完整值（系统只有单一HR用户） -->
              <div class="profile-field"><label>身份证号</label><span>{{ profile?.identity_card || '—' }}</span></div>
              <div class="profile-field"><label>性别</label><span>{{ getStatusLabel(genderMap, profile?.gender) }}</span></div>
              <div class="profile-field"><label>出生日期</label><span>{{ formatDate(profile?.birth_date) }}</span></div>
            </div>
          </div>

          <!-- 3. 户籍与地址 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <MapPin :size="16" />
              <span>户籍与地址</span>
            </div>
            <div class="profile-grid">
              <div class="profile-field"><label>户籍</label><span>{{ profile?.household_registration || '—' }}</span></div>
              <div class="profile-field"><label>居住地址</label><span>{{ profile?.residence_address || '—' }}</span></div>
              <div class="profile-field"><label>户口类型</label><span>{{ getStatusLabel(householdTypeMap, profile?.household_type) }}</span></div>
            </div>
          </div>

          <!-- 4. 教育信息 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <GraduationCap :size="16" />
              <span>教育信息</span>
            </div>
            <div class="profile-grid">
              <div class="profile-field"><label>学历</label><span>{{ getStatusLabel(educationLevelMap, profile?.education_level) }}</span></div>
              <div class="profile-field"><label>毕业院校</label><span>{{ profile?.graduation_school || '—' }}</span></div>
              <div class="profile-field"><label>专业</label><span>{{ profile?.major || '—' }}</span></div>
            </div>
          </div>

          <!-- 5. 当前任职 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <Briefcase :size="16" />
              <span>当前任职</span>
            </div>
            <div v-if="emp" class="profile-grid">
              <div class="profile-field"><label>部门</label><span>{{ emp.department || '—' }}</span></div>
              <div class="profile-field"><label>岗位</label><span>{{ emp.position || '—' }}</span></div>
              <div class="profile-field"><label>直属负责人</label><span>{{ emp.manager_name || '—' }}</span></div>
              <div class="profile-field"><label>分队</label><span>{{ emp.team_name || '—' }}</span></div>
              <div class="profile-field"><label>工作城市</label><span>{{ emp.work_city || '—' }}</span></div>
              <div class="profile-field"><label>办公方式</label><span>{{ getStatusLabel(workModeMap, emp.work_mode) }}</span></div>
              <div class="profile-field"><label>员工类型</label><span>{{ getStatusLabel(employmentTypeMap, emp.employment_type) }}</span></div>
              <div class="profile-field"><label>试用期</label><span>{{ emp.probation_months ? `${emp.probation_months} 个月` : '—' }}</span></div>
              <div class="profile-field"><label>试用期状态</label><span>{{ getStatusLabel(probationStatusMap, emp.probation_status) }}</span></div>
              <div class="profile-field"><label>预计入职日期</label><span>{{ formatDate(emp.expected_hire_date || emp.hire_date) }}</span></div>
              <div class="profile-field"><label>实际入职日期</label><span>{{ formatDate(emp.hire_date) }}</span></div>
              <div class="profile-field"><label>预计转正日期</label><span>{{ formatDate(emp.expected_regularization_date || emp.probation_end_date) }}</span></div>
              <div class="profile-field"><label>实际转正日期</label><span>{{ formatDate(emp.regularization_date) }}</span></div>
              <div class="profile-field"><label>雇佣状态</label><span>{{ getStatusLabel(employmentStatusMap, emp.employment_status) }}</span></div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无当前任职记录</div>
          </div>

          <!-- 6. 合同 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <FileText :size="16" />
              <span>合同</span>
            </div>
            <div v-if="fullProfile.contracts && fullProfile.contracts.length > 0">
              <div v-for="contract in fullProfile.contracts" :key="contract.id" class="list-item">
                <div class="list-item-grid">
                  <div class="profile-field"><label>签订公司</label><span>{{ contract.signing_company || '—' }}</span></div>
                  <div class="profile-field"><label>合同类型</label><span>{{ getStatusLabel(contractTypeMap, contract.contract_type) }}</span></div>
                  <div class="profile-field"><label>开始日期</label><span>{{ formatDate(contract.start_date) }}</span></div>
                  <div class="profile-field"><label>到期日期</label><span>{{ formatDate(contract.end_date) }}</span></div>
                  <div class="profile-field"><label>签订次数</label><span>{{ contract.signing_sequence ?? '—' }}</span></div>
                  <div class="profile-field"><label>合同状态</label><span><BaseBadge :label="getStatusLabel(contractStatusMap, contract.contract_status)" size="sm" /></span></div>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无合同记录</div>
          </div>

          <!-- 7. 薪酬 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <Banknote :size="16" />
              <span>薪酬</span>
            </div>
            <div v-if="fullProfile.compensations && fullProfile.compensations.length > 0">
              <div v-for="comp in fullProfile.compensations.slice(0, 1)" :key="comp.id" class="profile-grid">
                <div class="profile-field"><label>薪资原文</label><span>{{ comp.raw_salary_text || '—' }}</span></div>
                <div class="profile-field"><label>类型</label><span>{{ getStatusLabel(salaryTypeMap, comp.salary_type) }}</span></div>
                <div class="profile-field"><label>底薪</label><span>{{ comp.base_salary != null ? `${comp.base_salary} 元` : '—' }}</span></div>
                <div class="profile-field"><label>试用期薪资</label><span>{{ comp.probation_salary != null ? `${comp.probation_salary} 元` : '—' }}</span></div>
                <div class="profile-field"><label>转正薪资</label><span>{{ comp.regular_salary != null ? `${comp.regular_salary} 元` : '—' }}</span></div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无薪酬记录</div>
          </div>

          <!-- 8. 银行卡与支付宝 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <CreditCard :size="16" />
              <span>银行卡与支付宝</span>
            </div>
            <div v-if="fullProfile.financial_accounts && fullProfile.financial_accounts.length > 0">
              <div v-for="account in fullProfile.financial_accounts" :key="account.id" class="list-item">
                <div class="list-item-grid">
                  <div class="profile-field"><label>类型</label><span>{{ getStatusLabel(accountTypeMap, account.account_type) }}</span></div>
                  <div class="profile-field"><label>账号</label><span>{{ maskAccountNo(account.account_no) }}</span></div>
                  <div class="profile-field"><label>开户行</label><span>{{ account.bank_name || '—' }}</span></div>
                  <div class="profile-field"><label>主要账号</label><span>{{ account.is_primary ? '是' : '否' }}</span></div>
                  <div class="profile-field"><label>状态</label><span>{{ getStatusLabel(accountStatusMap, account.account_status) }}</span></div>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无银行卡或支付宝记录</div>
          </div>

          <!-- 9. 社保与公积金 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <Shield :size="16" />
              <span>社保与公积金</span>
            </div>
            <div class="profile-grid">
              <div class="profile-field"><label>社保状态</label><span>{{ getStatusLabel(socialInsuranceStatusMap, profile?.social_insurance_status) }}</span></div>
              <div class="profile-field"><label>社保规则</label><span>{{ getStatusLabel(benefitPolicyMap, profile?.social_insurance_policy) }}</span></div>
              <div class="profile-field"><label>社保开始日期</label><span>{{ formatDate(profile?.social_insurance_start_date) }}</span></div>
              <div class="profile-field"><label>公积金状态</label><span>{{ getStatusLabel(housingFundStatusMap, profile?.housing_fund_status) }}</span></div>
              <div class="profile-field"><label>公积金规则</label><span>{{ getStatusLabel(benefitPolicyMap, profile?.housing_fund_policy) }}</span></div>
              <div class="profile-field"><label>公积金开始日期</label><span>{{ formatDate(profile?.housing_fund_start_date) }}</span></div>
              <div class="profile-field"><label>花名册原文</label><span>{{ profile?.benefit_raw_text || '—' }}</span></div>
            </div>
          </div>

          <!-- 10. MBTI / PDP -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <Brain :size="16" />
              <span>MBTI / PDP</span>
            </div>
            <div v-if="fullProfile.assessments && fullProfile.assessments.length > 0">
              <div v-for="assessment in fullProfile.assessments" :key="assessment.id" class="list-item">
                <div class="list-item-grid">
                  <div class="profile-field"><label>测评类型</label><span>{{ getStatusLabel(assessmentTypeMap, assessment.assessment_type) }}</span></div>
                  <div class="profile-field"><label>结果</label><span>{{ assessment.result_text || '—' }}</span></div>
                  <div class="profile-field"><label>测评日期</label><span>{{ formatDate(assessment.assessment_date) }}</span></div>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无测评记录</div>
          </div>

          <!-- 11. 备注 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <StickyNote :size="16" />
              <span>备注</span>
            </div>
            <div v-if="fullProfile.notes && fullProfile.notes.length > 0">
              <div v-for="note in fullProfile.notes" :key="note.id" class="note-item">
                <div class="note-content">{{ note.content }}</div>
                <div class="note-meta">{{ formatDateTime(note.created_at) }}</div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无备注</div>
          </div>

          <!-- 12. 资料变更历史 -->
          <div class="profile-card card">
            <div class="profile-card-header">
              <History :size="16" />
              <span>资料变更历史</span>
            </div>
            <div v-if="fullProfile.attribute_history && fullProfile.attribute_history.length > 0">
              <div v-for="item in fullProfile.attribute_history" :key="item.id" class="history-item">
                <div class="history-dot"></div>
                <div class="history-body">
                  <div class="history-field">{{ item.field_name }}</div>
                  <div class="history-change">
                    <span class="history-old">{{ item.before_value ?? '空' }}</span>
                    <span class="history-arrow">→</span>
                    <span class="history-new">{{ item.after_value ?? '空' }}</span>
                  </div>
                  <div class="history-meta">
                    <span>{{ formatDateTime(item.created_at) }}</span>
                    <span v-if="item.source_type" class="history-source">{{ item.source_type }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-tertiary">暂无变更记录</div>
          </div>
        </template>
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
            <LifecycleBadge :status="resolveLifecycleStage(emp)" size="sm" />
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

.pending-info-card {
  padding: 12px 16px;
  background: var(--color-bg);
}

/* Full Profile */
.full-profile {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.profile-card {
  padding: 20px;
}
.profile-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
}
.profile-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.profile-field label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.profile-field span {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}
.list-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}
.list-item:last-child {
  border-bottom: none;
}
.list-item-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 24px;
}
.note-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}
.note-item:last-child {
  border-bottom: none;
}
.note-content {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  line-height: 1.5;
}
.note-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.history-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}
.history-item:last-child {
  border-bottom: none;
}
.history-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
  margin-top: 5px;
}
.history-body {
  flex: 1;
}
.history-field {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.history-change {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}
.history-old {
  color: var(--color-text-tertiary);
  text-decoration: line-through;
}
.history-arrow {
  margin: 0 6px;
  color: var(--color-text-tertiary);
}
.history-new {
  color: var(--color-primary);
  font-weight: 500;
}
.history-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  display: flex;
  gap: 8px;
}
.history-source {
  color: var(--color-text-tertiary);
}

@media (max-width: 1024px) {
  .detail-columns {
    grid-template-columns: 1fr;
  }
  .profile-grid,
  .list-item-grid {
    grid-template-columns: 1fr;
  }
}
</style>
