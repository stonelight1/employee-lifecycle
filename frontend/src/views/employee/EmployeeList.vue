<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { get, del } from '@/api'
import { formatDate } from '@/utils/date'
import {
  getStatusLabel,
  contractStatusMap,
  contractTypeMap,
  socialInsuranceStatusMap,
  housingFundStatusMap,
  profileCompletenessMap,
  genderMap,
} from '@/constants/status'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmployeeAvatar from '@/components/business/EmployeeAvatar.vue'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import type { EmployeeListItem, EmployeeListData } from '@/types'
import { Upload, Plus, MoreHorizontal, ChevronUp, ChevronDown, ArrowUpDown } from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

// ====== 数据状态 ======
const employees = ref<EmployeeListItem[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref(false)
const page = ref(1)
const pageSize = ref(20)
const openMenuId = ref<number | null>(null)
const sortBy = ref<string>('default')
const sortOrder = ref<string>('asc')

// ====== 分页计算 ======
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const showingFrom = computed(() => (page.value - 1) * pageSize.value + 1)
const showingTo = computed(() => Math.min(page.value * pageSize.value, total.value))

// ====== 是否有激活的筛选条件 ======
const hasActiveFilters = computed(() =>
  !!(route.query.keyword || route.query.lifecycle_stage || route.query.risk_level)
)

// ====== URL 查询变化时重新加载 ======
watch(() => route.query, () => {
  if (route.query.page) {
    page.value = Number(route.query.page)
  } else {
    page.value = 1
  }
  if (route.query.sort_by) {
    sortBy.value = route.query.sort_by as string
  } else {
    sortBy.value = 'default'
  }
  if (route.query.sort_order) {
    sortOrder.value = route.query.sort_order as string
  } else {
    sortOrder.value = route.query.lifecycle_stage ? 'asc' : 'asc'
  }
  loadEmployees()
}, { immediate: true, deep: true })

// ====== 分页大小变化时重置 ======
watch(pageSize, () => {
  page.value = 1
  router.replace({ query: { ...route.query, page: undefined } })
  loadEmployees()
})

// ====== 排序切换 ======
function toggleSort(field: string) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortOrder.value = 'asc'
  }
  page.value = 1
  router.replace({
    query: {
      ...route.query,
      sort_by: sortBy.value !== 'default' ? sortBy.value : undefined,
      sort_order: sortOrder.value !== 'asc' ? sortOrder.value : undefined,
      page: undefined,
    },
  })
  loadEmployees()
}

function sortIcon(field: string): string {
  if (sortBy.value !== field) return 'none'
  return sortOrder.value === 'asc' ? 'asc' : 'desc'
}

// ====== 加载员工列表 ======
async function loadEmployees() {
  loading.value = true
  error.value = false
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    const q = route.query
    if (q.keyword) params.keyword = q.keyword as string
    if (q.lifecycle_stage) params.lifecycle_stage = q.lifecycle_stage as string
    if (q.risk_level) params.risk_level = q.risk_level as string

    const res = await get<EmployeeListData>('/employees', params)
    if (res.success && res.data) {
      employees.value = res.data.items || []
      total.value = res.data.total
    } else {
      error.value = true
    }
  } catch (e: any) {
    error.value = true
    console.error('加载员工列表失败:', e)
  } finally {
    loading.value = false
  }
}

// ====== 翻页 ======
function goToPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  router.replace({ query: { ...route.query, page: p > 1 ? String(p) : undefined } })
}

// ====== 更多操作菜单 ======
function toggleMenu(id: number) {
  openMenuId.value = openMenuId.value === id ? null : id
}
function closeMenu() {
  openMenuId.value = null
}

// ====== 查看详情 ======
function goToDetail(emp: EmployeeListItem) {
  router.push(`/employees/${emp.id}`)
}

// ====== 删除员工 ======
function confirmDelete(emp: EmployeeListItem) {
  closeMenu()
  confirm({
    title: '确认删除员工',
    message: `确定要删除员工「${emp.name}」吗？此操作不可恢复。`,
    confirmText: '确认删除',
    danger: true,
    onConfirm: async () => {
      try {
        await del(`/employees/${emp.id}`)
        showToast({ message: '员工已删除', type: 'success' })
        await loadEmployees()
      } catch (e: any) {
        showToast({ message: e.message || '删除失败', type: 'error' })
      }
    },
  })
}

// ====== 点击下一事项 ======
function goToNextAction(emp: EmployeeListItem) {
  if (!emp.next_action) return
  const action = emp.next_action
  const baseType = action.source_type
  if (baseType === 'FOLLOWUP_TASK') {
    router.push(`/followup-tasks/${action.id}`)
  } else if (baseType === 'HR_CONFIRMATION') {
    router.push(`/confirmations/${action.id}`)
  } else if (baseType === 'REGULARIZATION') {
    router.push(`/employees/${emp.id}/regularization`)
  } else if (baseType === 'PENDING_EMPLOYMENT') {
    router.push(`/employees/${emp.id}/employment`)
  } else if (baseType === 'TODO') {
    router.push(`/todos/${action.id}`)
  } else {
    router.push(`/employees/${emp.id}`)
  }
}

// ====== 辅助展示函数 ======

function calcAge(age?: number | null): string {
  if (age === null || age === undefined) return '年龄未知'
  return `${age}岁`
}

function displayGender(gender?: string | null): string {
  if (!gender) return '性别未知'
  return getStatusLabel(genderMap, gender)
}

function displayIdCard(idCard?: string | null): string {
  if (!idCard) return '未填写身份证'
  return idCard
}

function displayMobile(mobile?: string | null): string {
  if (!mobile) return '未填写手机号'
  return mobile
}

function displayTenure(text?: string | null): string {
  if (!text) return ''
  return `司龄${text}`
}

function joinParts(parts: (string | null | undefined)[], sep: string = ' · '): string {
  const filtered = parts.filter((p): p is string => !!p)
  return filtered.length > 0 ? filtered.join(sep) : ''
}

function contractLabel(emp: EmployeeListItem): string {
  const status = emp.contract_status
  const ctype = emp.contract_type
  if (!status && !ctype) return '未录入合同'
  const label = getStatusLabel(contractStatusMap, status)
  if (ctype === 'INDEFINITE') return `${label} · 无固定期限`
  if (ctype === 'FIXED_TERM' && emp.contract_end_date) {
    return `${label} · ${emp.contract_end_date}到期`
  }
  return label || '未录入合同'
}

function benefitLabel(status?: string | null, map: Record<string, string> = {}): string {
  if (!status) return '未填写'
  return getStatusLabel(map, status)
}

function colSortClass(field: string): string {
  if (sortBy.value !== field) return ''
  return sortOrder.value === 'asc' ? 'sorted-asc' : 'sorted-desc'
}
</script>

<template>
  <div class="page" @click="closeMenu">
    <!-- 页面标题 -->
    <PageHeader title="员工中心" subtitle="统一查看员工状态、试用期进度和下一步事项">
      <template #actions>
        <BaseButton variant="primary" @click="router.push('/roster-imports/new?from=employees')">
          <Upload :size="16" /> 导入花名册
        </BaseButton>
        <BaseButton variant="secondary" @click="router.push('/employees/new')">
          <Plus :size="16" /> 新增员工
        </BaseButton>
      </template>
    </PageHeader>

    <!-- 错误状态 -->
    <div v-if="error && !loading" class="card error-card">
      <div class="error-message">
        <p>员工列表加载失败</p>
        <BaseButton variant="primary" @click="loadEmployees()">重新加载</BaseButton>
      </div>
    </div>

    <!-- 表格区域 -->
    <div v-if="!error" class="table-wrapper card">
      <!-- 骨架屏加载 -->
      <div v-if="loading && employees.length === 0" class="table-skeleton">
        <div v-for="n in 5" :key="n" class="skeleton-row">
          <div class="skeleton-cell" style="flex: 0 0 190px;"><div class="skeleton-line w-28" /><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell" style="flex: 0 0 220px;"><div class="skeleton-line w-28" /><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell" style="flex: 0 0 220px;"><div class="skeleton-line w-28" /><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell" style="flex: 0 0 145px;"><div class="skeleton-line w-20" /><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell" style="flex: 0 0 220px;"><div class="skeleton-line w-28" /><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell" style="flex: 0 0 190px;"><div class="skeleton-line w-24" /><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell" style="flex: 0 0 135px;"><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell" style="flex: 0 0 160px;"><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell" style="flex: 0 0 90px;"><div class="skeleton-line w-12" /></div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading && employees.length === 0 && !hasActiveFilters">
        <BaseEmpty title="还没有员工档案" description="可以新增员工或导入花名册" />
      </div>
      <div v-else-if="!loading && employees.length === 0">
        <BaseEmpty title="没有找到符合条件的员工" description="请调整搜索词或筛选条件" />
      </div>

      <!-- 数据表格 -->
      <div v-if="employees.length > 0" class="table-scroll">
        <table>
          <thead>
            <tr>
              <th class="col-employee">
                员工
                <button class="sort-btn" :class="colSortClass('name')" @click="toggleSort('name')">
                  <ArrowUpDown :size="14" v-if="sortBy !== 'name'" />
                  <ChevronUp :size="14" v-else-if="sortOrder === 'asc'" />
                  <ChevronDown :size="14" v-else />
                </button>
              </th>
              <th class="col-identity">身份信息</th>
              <th class="col-employment">任职信息</th>
              <th class="col-hire">
                入职信息
                <button class="sort-btn" :class="colSortClass('actual_hire_date')" @click="toggleSort('actual_hire_date')">
                  <ArrowUpDown :size="14" v-if="sortBy !== 'actual_hire_date'" />
                  <ChevronUp :size="14" v-else-if="sortOrder === 'asc'" />
                  <ChevronDown :size="14" v-else />
                </button>
              </th>
              <th class="col-probation">
                试用进度
                <button class="sort-btn" :class="colSortClass('probation_progress')" @click="toggleSort('probation_progress')">
                  <ArrowUpDown :size="14" v-if="sortBy !== 'probation_progress'" />
                  <ChevronUp :size="14" v-else-if="sortOrder === 'asc'" />
                  <ChevronDown :size="14" v-else />
                </button>
              </th>
              <th class="col-contract">合同与福利</th>
              <th class="col-status">
                状态与风险
                <button class="sort-btn" :class="colSortClass('risk_level')" @click="toggleSort('risk_level')">
                  <ArrowUpDown :size="14" v-if="sortBy !== 'risk_level'" />
                  <ChevronUp :size="14" v-else-if="sortOrder === 'asc'" />
                  <ChevronDown :size="14" v-else />
                </button>
              </th>
              <th class="col-next">下一事项</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="emp in employees" :key="emp.id" class="emp-row" @click="goToDetail(emp)">
              <!-- 1. 员工列 -->
              <td class="td-employee" @click.stop>
                <div class="emp-cell">
                  <EmployeeAvatar :name="emp.name" size="sm" />
                  <div class="emp-info">
                    <span class="emp-name" :title="emp.name">{{ emp.name }}</span>
                    <span class="emp-meta">{{ emp.employee_no || '' }}</span>
                    <span class="emp-meta">{{ displayMobile(emp.mobile) }}</span>
                  </div>
                </div>
              </td>

              <!-- 2. 身份信息列 -->
              <td class="td-identity">
                <div class="identity-row">{{ displayGender(emp.gender) }}{{ emp.gender && (emp.age !== null && emp.age !== undefined) ? ' · ' : '' }}{{ calcAge(emp.age) }}</div>
                <div class="identity-id-card">{{ displayIdCard(emp.identity_card) }}</div>
              </td>

              <!-- 3. 任职信息列 -->
              <td class="td-employment">
                <template v-if="emp.current_employment">
                  <div class="dept-pos-row">
                    {{ joinParts([emp.current_employment.department, emp.current_employment.position]) || '任职信息未完善' }}
                  </div>
                  <div class="team-city-row">
                    <template v-if="emp.current_employment.team_name">
                      {{ emp.current_employment.team_name }}<template v-if="emp.current_employment.work_city"> · </template>
                    </template>
                    <template v-if="emp.current_employment.work_city">
                      {{ emp.current_employment.work_city }}
                    </template>
                    <template v-if="emp.current_employment.work_mode === 'REMOTE'">
                      <template v-if="emp.current_employment.work_city || emp.current_employment.team_name"> · </template>远程
                    </template>
                  </div>
                </template>
                <span v-else class="text-muted">任职信息未完善</span>
              </td>

              <!-- 4. 入职信息列 -->
              <td class="td-hire">
                <template v-if="emp.actual_hire_date || emp.expected_hire_date">
                  <div class="hire-date-row">
                    {{ formatDate(emp.actual_hire_date || emp.expected_hire_date) }}{{ emp.actual_hire_date ? '入职' : '预计入职' }}
                  </div>
                  <div v-if="emp.current_tenure_text" class="tenure-row" :title="emp.total_tenure_text && emp.total_tenure_text !== emp.current_tenure_text ? `累计${emp.total_tenure_text}` : ''">
                    {{ displayTenure(emp.current_tenure_text) }}
                  </div>
                </template>
                <span v-else class="text-muted">缺少入职日期</span>
              </td>

              <!-- 5. 试用进度列 -->
              <td class="td-probation">
                <template v-if="emp.lifecycle_stage === 'PENDING'">
                  <span class="text-muted">尚未入职</span>
                </template>
                <template v-else-if="emp.probation_progress !== null && emp.lifecycle_stage !== 'ACTIVE'">
                  <div class="prob-progress-row" :class="{ 'prob-overdue': (emp.probation_overdue_days || 0) > 0, 'prob-soon': (emp.probation_days_remaining !== null && emp.probation_days_remaining !== undefined && emp.probation_days_remaining > 0 && emp.probation_days_remaining <= 7) }">
                    <span class="prob-pct">{{ emp.probation_progress }}%</span>
                    <div class="prob-bar-track">
                      <div class="prob-bar-fill" :style="{ width: emp.probation_progress + '%' }"></div>
                    </div>
                  </div>
                  <div class="prob-date-row">
                    <template v-if="emp.expected_regularization_date">
                      转正 {{ emp.expected_regularization_date }}
                    </template>
                  </div>
                  <div v-if="(emp.probation_overdue_days || 0) > 0" class="prob-overdue-text">
                    已逾期{{ emp.probation_overdue_days }}天
                  </div>
                  <div v-else-if="emp.probation_days_remaining !== null && emp.probation_days_remaining !== undefined && emp.probation_days_remaining > 0" class="prob-remaining-text">
                    剩余{{ emp.probation_days_remaining }}天
                  </div>
                </template>
                <template v-else-if="emp.lifecycle_stage === 'ACTIVE'">
                  <span class="text-muted">已转正</span>
                </template>
                <template v-else-if="emp.lifecycle_stage === 'REGULARIZATION_PENDING'">
                  <div class="prob-progress-row prob-overdue" v-if="emp.probation_overdue_days">
                    <span class="prob-pct">100%</span>
                    <div class="prob-bar-track">
                      <div class="prob-bar-fill" style="width: 100%"></div>
                    </div>
                  </div>
                  <div class="prob-date-row" v-if="emp.expected_regularization_date">
                    应转正 {{ emp.expected_regularization_date }}
                  </div>
                  <div v-if="(emp.probation_overdue_days || 0) > 0" class="prob-overdue-text">
                    已逾期{{ emp.probation_overdue_days }}天
                  </div>
                </template>
                <template v-else-if="!emp.current_employment">
                  <span class="text-muted">无法计算</span>
                </template>
                <template v-else>
                  <span class="text-muted">—</span>
                </template>
              </td>

              <!-- 6. 合同与福利列 -->
              <td class="td-contract">
                <div class="contract-row">{{ contractLabel(emp) }}</div>
                <div class="benefit-row">
                  社保：{{ benefitLabel(emp.social_insurance_status, socialInsuranceStatusMap) }}
                </div>
                <div class="benefit-row">
                  公积金：{{ benefitLabel(emp.housing_fund_status, housingFundStatusMap) }}
                </div>
              </td>

              <!-- 7. 状态与风险列 -->
              <td class="td-status-risk">
                <div class="status-risk-cell">
                  <LifecycleBadge :status="emp.lifecycle_stage" size="sm" />
                  <RiskBadge v-if="emp.risk?.level && emp.risk.level !== 'NONE'" :level="emp.risk.level" size="sm" />
                </div>
                <div v-if="emp.profile_completeness_status" class="completeness-row">
                  <span :class="emp.profile_completeness_status === 'INCOMPLETE' ? 'text-warning' : 'text-muted'">
                    {{ getStatusLabel(profileCompletenessMap, emp.profile_completeness_status) }}
                  </span>
                </div>
              </td>

              <!-- 8. 下一事项列 -->
              <td class="td-next" @click.stop="goToNextAction(emp)">
                <template v-if="emp.next_action">
                  <div class="next-text" :class="{
                    'urgency-overdue': emp.next_action.urgency === 'OVERDUE',
                    'urgency-today': emp.next_action.urgency === 'TODAY',
                    'urgency-soon': emp.next_action.urgency === 'SOON',
                  }">
                    {{ emp.next_action.title }}
                  </div>
                  <div v-if="emp.next_action.urgency === 'OVERDUE'" class="next-sub overdue">
                    已逾期{{ emp.next_action.overdue_days }}天
                  </div>
                  <div v-else-if="emp.next_action.urgency === 'TODAY'" class="next-sub today">
                    今天到期
                  </div>
                  <div v-else-if="emp.next_action.urgency === 'SOON'" class="next-sub soon">
                    {{ emp.next_action.days_remaining }}天后到期
                  </div>
                  <div v-else-if="emp.next_action.due_at" class="next-sub">
                    {{ emp.next_action.due_at }}
                  </div>
                  <div v-else-if="emp.next_action.source_type === 'HR_CONFIRMATION'" class="next-sub">
                    待HR确认
                  </div>
                </template>
                <span v-else class="text-muted">暂无待办</span>
              </td>

              <!-- 9. 操作列 -->
              <td class="td-actions" @click.stop>
                <div class="action-group">
                  <button class="action-link" @click="goToDetail(emp)">查看</button>
                  <div class="dropdown-wrap">
                    <button class="action-icon-btn" @click.stop="toggleMenu(emp.id)">
                      <MoreHorizontal :size="16" />
                    </button>
                    <div v-if="openMenuId === emp.id" class="dropdown-menu" @click.stop>
                      <button class="dropdown-item" @click="goToDetail(emp)">编辑资料</button>
                      <button class="dropdown-item" @click="goToDetail(emp)">查看档案</button>
                      <button class="dropdown-item" @click="goToDetail(emp)">记录沟通</button>
                      <button v-if="emp.lifecycle_stage !== 'SEPARATED'" class="dropdown-item" @click="goToDetail(emp)">发起异动</button>
                      <button v-if="emp.lifecycle_stage !== 'SEPARATED'" class="dropdown-item" @click="goToDetail(emp)">办理离职</button>
                      <div class="dropdown-divider" />
                      <button class="dropdown-item dropdown-danger" @click="confirmDelete(emp)">删除员工</button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 分页栏 -->
    <div v-if="total > 0" class="pagination-bar">
      <div class="pagination-info text-sm text-tertiary">
        共 {{ total }} 名员工，显示第 {{ showingFrom }} ~ {{ showingTo }} 名
      </div>
      <div class="pagination-controls">
        <button class="page-btn" :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
        <template v-for="p in totalPages" :key="p">
          <button v-if="p === 1 || p === totalPages || Math.abs(p - page) <= 2" class="page-btn page-num" :class="{ active: p === page }" @click="goToPage(p)">{{ p }}</button>
          <span v-else-if="p === page - 3 || p === page + 3" class="page-ellipsis">…</span>
        </template>
        <button class="page-btn" :disabled="page >= totalPages" @click="goToPage(page + 1)">下一页</button>
        <select v-model="pageSize" class="page-size-select">
          <option :value="10">10条/页</option>
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
        </select>
      </div>
    </div>

    <BaseModal :show="showConfirm" :title="confirmOpts.title" :message="confirmOpts.message" :confirm-text="confirmOpts.confirmText" :danger="confirmOpts.danger" @confirm="handleConfirm" @cancel="handleCancel" />
  </div>
</template>

<style scoped>
/* ===== 错误状态 ===== */
.error-card { padding: 40px; text-align: center; }
.error-message p { margin: 0 0 16px; color: var(--color-danger); font-size: var(--font-size-sm); }

/* ===== 表格容器 ===== */
.table-wrapper {
  overflow: visible;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  min-width: 1150px;
}
th, td {
  padding: 10px 10px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  line-height: 1.45;
  vertical-align: middle;
}
th {
  background: var(--color-surface-secondary);
  font-weight: 600;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding-top: 9px;
  padding-bottom: 9px;
  user-select: none;
}

/* 列宽 */
.col-employee { width: 190px; }
.col-identity { width: 210px; }
.col-employment { width: 210px; }
.col-hire { width: 140px; }
.col-probation { width: 200px; }
.col-contract { width: 180px; }
.col-status { width: 130px; }
.col-next { width: 155px; }
.col-actions { width: 85px; }

/* 排序按钮 */
.sort-btn {
  background: none;
  border: none;
  cursor: pointer;
  vertical-align: middle;
  padding: 0 2px;
  color: var(--color-text-tertiary);
  display: inline-flex;
  align-items: center;
  opacity: 0.5;
  transition: opacity 0.12s;
}
.sort-btn:hover {
  opacity: 1;
  color: var(--color-primary);
}
.sort-btn.sorted-asc,
.sort-btn.sorted-desc {
  opacity: 1;
  color: var(--color-primary);
}

/* ===== 行 ===== */
.emp-row {
  cursor: pointer;
  transition: background 0.12s;
}
.emp-row:hover td {
  background: var(--color-bg);
}
.emp-row:last-child td {
  border-bottom: none;
}

/* ===== 1. 员工列 ===== */
.td-employee { vertical-align: middle; }
.emp-cell {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.emp-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.5;
}
.emp-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.emp-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 2. 身份信息 ===== */
.td-identity { vertical-align: middle; }
.identity-row {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.identity-id-card {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 3. 任职信息 ===== */
.td-employment { vertical-align: middle; }
.dept-pos-row {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.team-city-row {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 4. 入职信息 ===== */
.td-hire { vertical-align: middle; }
.hire-date-row {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
}
.tenure-row {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 1px;
  white-space: nowrap;
}

/* ===== 5. 试用进度 ===== */
.td-probation { vertical-align: middle; }
.prob-progress-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}
.prob-pct {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--color-primary);
  min-width: 32px;
  text-align: right;
  flex-shrink: 0;
}
.prob-progress-row.prob-overdue .prob-pct { color: var(--color-danger); }
.prob-progress-row.prob-soon .prob-pct { color: var(--color-warning); }
.prob-bar-track {
  flex: 1;
  height: 4px;
  background: var(--color-border);
  border-radius: 99px;
  overflow: hidden;
}
.prob-bar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 99px;
  transition: width 0.3s ease;
}
.prob-overdue .prob-bar-fill { background: var(--color-danger); }
.prob-soon .prob-bar-fill { background: var(--color-warning); }
.prob-date-row {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.prob-overdue-text {
  font-size: var(--font-size-xs);
  color: var(--color-danger);
  font-weight: 500;
}
.prob-remaining-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.prob-soon .prob-remaining-text { color: var(--color-warning); }

/* ===== 6. 合同与福利 ===== */
.td-contract { vertical-align: middle; }
.contract-row {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.benefit-row {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 7. 状态与风险 ===== */
.td-status-risk { vertical-align: middle; }
.status-risk-cell {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.completeness-row {
  margin-top: 3px;
  font-size: var(--font-size-xs);
}
.text-warning { color: var(--color-warning); font-weight: 500; }

/* ===== 8. 下一事项 ===== */
.td-next { vertical-align: middle; cursor: pointer; }
.next-text {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.next-text.urgency-overdue { color: var(--color-danger); }
.next-text.urgency-today { color: var(--color-warning); }
.next-text.urgency-soon { color: var(--color-warning); }
.next-sub {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 1px;
  white-space: nowrap;
}
.next-sub.overdue { color: var(--color-danger); font-weight: 500; }
.next-sub.today { color: var(--color-warning); font-weight: 500; }
.next-sub.soon { color: var(--color-warning); }

/* ===== 9. 操作列 ===== */
.td-actions {
  white-space: nowrap;
  vertical-align: middle;
}
.action-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.action-link {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.12s;
}
.action-link:hover { background: var(--color-primary-soft); }
.action-icon-btn {
  background: none;
  border: none;
  border-radius: 6px;
  padding: 4px 6px;
  cursor: pointer;
  color: var(--color-text-tertiary);
  display: inline-flex;
  align-items: center;
  transition: all 0.12s;
}
.action-icon-btn:hover { background: var(--color-bg); color: var(--color-text-secondary); }
.dropdown-wrap { position: relative; display: inline-block; }
.dropdown-menu {
  position: absolute; right: 0; top: 100%; margin-top: 4px;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-popover);
  min-width: 130px;
  z-index: 100;
  padding: 4px;
}
.dropdown-item {
  display: block; width: 100%; padding: 7px 12px;
  border: none; background: none;
  font-size: var(--font-size-sm); color: var(--color-text-primary);
  cursor: pointer; text-align: left; border-radius: 4px;
}
.dropdown-item:hover { background: var(--color-bg); }
.dropdown-danger { color: var(--color-danger) !important; }
.dropdown-divider { height: 1px; background: var(--color-border); margin: 4px 0; }

/* ===== 分页 ===== */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 8px 0;
}
.pagination-info { font-size: var(--font-size-sm); color: var(--color-text-tertiary); }
.pagination-controls { display: flex; align-items: center; gap: 4px; }
.page-btn {
  padding: 5px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  cursor: pointer;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  transition: all 0.12s;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.page-btn.active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.page-num { min-width: 32px; text-align: center; padding: 5px 8px; }
.page-ellipsis { padding: 0 4px; color: var(--color-text-tertiary); }
.page-size-select {
  margin-left: 8px;
  padding: 5px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  cursor: pointer;
}

/* ===== 文本工具 ===== */
.text-muted { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.text-sm { font-size: var(--font-size-sm); }
.text-xs { font-size: var(--font-size-xs); }
.text-tertiary { color: var(--color-text-tertiary); }

/* ===== 骨架屏 ===== */
.table-skeleton { padding: 0 16px; }
.skeleton-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
}
.skeleton-row:last-child { border-bottom: none; }
.skeleton-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: 4px;
  animation: shimmer 1.5s infinite;
}
.w-12 { width: 48px; }
.w-16 { width: 64px; }
.w-20 { width: 80px; }
.w-24 { width: 96px; }
.w-28 { width: 112px; }
.w-32 { width: 128px; }

@keyframes shimmer {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

/* ===== 响应式 ===== */
@media (max-width: 1280px) {
  .col-employee { width: 170px; }
  .col-identity { width: 180px; }
  .col-employment { width: 180px; }
  .col-hire { width: 130px; }
  .col-probation { width: 180px; }
  .col-contract { width: 160px; }
  .col-status { width: 120px; }
  .col-next { width: 140px; }
}

@media (max-width: 1024px) {
  .col-employee { width: 150px; }
  .col-identity { width: 160px; }
  .col-employment { width: 160px; }
  .col-hire { width: 120px; }
  .col-probation { width: 170px; }
  .col-contract { width: 140px; }
  .col-status { width: 110px; }
  .col-next { width: 130px; }

  /* 1024px 隐藏次要信息 */
  .emp-meta:first-of-type { display: none; } /* 隐藏员工编号 */
  .contract-row { font-size: var(--font-size-xs); }
  .completeness-row { display: none; }
}
</style>
