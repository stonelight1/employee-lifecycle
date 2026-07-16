<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { get, del } from '@/api'
import { formatDate, calculateOverdueDays } from '@/utils/date'
import { getStatusLabel, employmentStatusMap } from '@/constants/status'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import EmployeeAvatar from '@/components/business/EmployeeAvatar.vue'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import type { EmployeeListItem, EmployeeListData } from '@/types'
import { Upload, Plus, MoreHorizontal } from 'lucide-vue-next'

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
const pageSize = ref(10)
const openMenuId = ref<number | null>(null)

// ====== 分页计算 ======
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const showingFrom = computed(() => (page.value - 1) * pageSize.value + 1)
const showingTo = computed(() => Math.min(page.value * pageSize.value, total.value))

// ====== 是否有激活的筛选条件（用于空状态提示） ======
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
  loadEmployees()
}, { immediate: true, deep: true })

// ====== 分页大小变化时重置 ======
watch(pageSize, () => {
  page.value = 1
  router.replace({ query: { ...route.query, page: undefined } })
  loadEmployees()
})

// ====== 加载员工列表 ======
async function loadEmployees() {
  loading.value = true
  error.value = false
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
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

// ====== 任职信息的 tooltip ======
function deptPosTitle(emp: { department?: string | null; position?: string | null }): string {
  const parts: string[] = []
  if (emp.department) parts.push(emp.department)
  if (emp.position) parts.push(emp.position)
  return parts.join(' · ') || ''
}

// ====== 格式化短日期 ======
function shortDate(dateStr?: string | null): string {
  if (!dateStr) return ''
  const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return dateStr
  return `${parseInt(match[2])}月${parseInt(match[3])}日`
}

// ====== 年龄计算 ======
function calcAge(birthDate?: string | null): number {
  if (!birthDate) return 0
  const d = new Date(birthDate)
  if (isNaN(d.getTime())) return 0
  const today = new Date()
  let age = today.getFullYear() - d.getFullYear()
  const m = today.getMonth() - d.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age--
  return age
}

// ====== 身份证号脱敏 ======
function maskIdCard(idCard?: string | null): string {
  if (!idCard) return ''
  if (idCard.length < 10) return idCard
  return idCard.slice(0, 4) + '**********' + idCard.slice(-4)
}
</script>

<template>
  <div class="page" @click="closeMenu">
    <!-- 页面标题 -->
    <div class="page-intro">
      <h1 class="page-title">员工中心</h1>
      <p class="page-subtitle">统一查看员工状态、试用期进度和下一步事项</p>
      <div class="page-actions">
        <button class="action-btn primary" @click="router.push('/roster-imports/new?from=employees')">
          <Upload :size="16" /> 导入花名册
        </button>
        <button class="action-btn" @click="router.push('/employees/new')">
          <Plus :size="16" /> 新增员工
        </button>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-if="error && !loading" class="card error-card">
      <div class="error-message">
        <p>员工列表加载失败</p>
        <button class="action-btn" @click="loadEmployees()">重新加载</button>
      </div>
    </div>

    <!-- 表格区域 -->
    <div v-if="!error" class="table-wrapper card">
      <!-- 骨架屏加载 -->
      <div v-if="loading && employees.length === 0" class="table-skeleton">
        <div v-for="n in 5" :key="n" class="skeleton-row">
          <div class="skeleton-cell skeleton-cell-employee">
            <div class="skeleton-avatar" />
            <div class="skeleton-lines">
              <div class="skeleton-line w-24" />
              <div class="skeleton-line w-32" />
            </div>
          </div>
          <div class="skeleton-cell"><div class="skeleton-line w-28" /><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell"><div class="skeleton-line w-28" /><div class="skeleton-line w-20" /></div>
          <div class="skeleton-cell"><div class="skeleton-line w-20" /><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell"><div class="skeleton-line w-28" /><div class="skeleton-line w-16" /></div>
          <div class="skeleton-cell skeleton-cell-actions"><div class="skeleton-line w-12" /></div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading && employees.length === 0 && !hasActiveFilters">
        <BaseEmpty
          title="还没有员工档案"
          description="可以新增员工或导入花名册"
        />
      </div>
      <div v-else-if="!loading && employees.length === 0">
        <BaseEmpty
          title="没有找到符合条件的员工"
          description="请调整搜索词或筛选条件"
        />
      </div>

      <!-- 数据表格 -->
      <table v-if="employees.length > 0">
        <thead>
          <tr>
            <th class="col-employee">员工</th>
            <th class="col-employment">任职信息</th>
            <th class="col-probation">入职与试用</th>
            <th class="col-status">状态与风险</th>
            <th class="col-next">接下来</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="emp in employees" :key="emp.id" class="emp-row">
            <!-- 1. 员工列 -->
            <td class="td-employee">
              <div class="emp-cell hover-trigger">
                <EmployeeAvatar :name="emp.name" size="sm" />
                <div class="emp-info">
                  <div class="emp-name-row">
                    <span class="emp-name">{{ emp.name }}</span>
                    <span v-if="emp.birth_date" class="emp-age">{{ calcAge(emp.birth_date) }}岁</span>
                  </div>
                  <span v-if="emp.employee_no || emp.mobile || emp.gender" class="emp-meta">
                    <template v-if="emp.gender">{{ emp.gender === 'MALE' ? '男' : emp.gender === 'FEMALE' ? '女' : emp.gender }}</template>
                    <template v-if="emp.gender && (emp.employee_no || emp.mobile)"> · </template>
                    <template v-if="emp.employee_no">{{ emp.employee_no }}</template>
                    <template v-if="emp.employee_no && emp.mobile"> · </template>
                    <template v-if="emp.mobile">{{ emp.mobile }}</template>
                  </span>
                </div>
                <!-- hover 浮层 -->
                <div class="emp-hover-card">
                  <div class="hover-card-item">
                    <span class="hover-card-label">邮箱</span>
                    <span class="hover-card-value">{{ emp.email || '—' }}</span>
                  </div>
                  <div class="hover-card-item">
                    <span class="hover-card-label">身份证号</span>
                    <span class="hover-card-value">{{ emp.identity_card ? maskIdCard(emp.identity_card) : '—' }}</span>
                  </div>
                  <div class="hover-card-item">
                    <span class="hover-card-label">公司主体</span>
                    <span class="hover-card-value">{{ emp.signing_company || '—' }}</span>
                  </div>
                </div>
              </div>
            </td>

            <!-- 2. 任职信息列 -->
            <td class="td-employment">
              <template v-if="emp.current_employment">
                <div class="emp-dept-pos" :title="deptPosTitle(emp.current_employment)">
                  <template v-if="emp.current_employment.department && emp.current_employment.position">
                    {{ emp.current_employment.department }} · {{ emp.current_employment.position }}
                  </template>
                  <template v-else-if="emp.current_employment.department">
                    {{ emp.current_employment.department }}
                  </template>
                  <template v-else-if="emp.current_employment.position">
                    {{ emp.current_employment.position }}
                  </template>
                  <template v-else>
                    <span class="text-muted">—</span>
                  </template>
                </div>
                <div v-if="emp.current_employment.team_name" class="emp-team">
                  {{ emp.current_employment.team_name }}
                </div>
                <div class="emp-status-tag">
                  {{ getStatusLabel(employmentStatusMap, emp.current_employment.employment_status) }}
                </div>
              </template>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- 3. 入职与试用列 -->
            <td class="td-probation">
              <template v-if="emp.lifecycle_stage === 'PENDING' && emp.current_employment">
                <div class="prob-row">{{ shortDate(emp.current_employment.expected_hire_date) || formatDate(emp.current_employment.hire_date) }} 预计入职</div>
                <div class="text-muted">尚未入职</div>
              </template>
              <template v-else-if="emp.lifecycle_stage === 'PROBATION' && emp.current_employment">
                <div class="prob-row">
                  {{ formatDate(emp.current_employment.actual_hire_date || emp.current_employment.hire_date) }} 入职
                </div>
                <div v-if="emp.current_employment.expected_regularization_date || emp.current_employment.probation_end_date" class="prob-row-sub">
                  转正 {{ formatDate(emp.current_employment.expected_regularization_date || emp.current_employment.probation_end_date) }}
                </div>
                <div v-if="emp.probation_progress !== null" class="prob-bar">
                  <span class="prob-bar-label">{{ emp.probation_progress }}%</span>
                  <div class="prob-bar-track">
                    <div class="prob-bar-fill" :style="{ width: emp.probation_progress + '%' }"></div>
                  </div>
                </div>
              </template>
              <template v-else-if="emp.lifecycle_stage === 'REGULARIZATION_PENDING' && emp.current_employment">
                <div class="prob-row">{{ formatDate(emp.current_employment.actual_hire_date || emp.current_employment.hire_date) }} 入职</div>
                <div class="prob-row-sub" v-if="emp.current_employment.expected_regularization_date || emp.current_employment.probation_end_date">
                  应转正 {{ formatDate(emp.current_employment.expected_regularization_date || emp.current_employment.probation_end_date) }}
                </div>
                <div v-if="emp.current_employment.probation_end_date && calculateOverdueDays(emp.current_employment.probation_end_date) > 0" class="overdue-text">
                  已超期 {{ calculateOverdueDays(emp.current_employment.probation_end_date) }} 天
                </div>
              </template>
              <template v-else-if="emp.lifecycle_stage === 'ACTIVE' && emp.current_employment">
                <div class="prob-row">{{ formatDate(emp.current_employment.actual_hire_date || emp.current_employment.hire_date) }} 入职</div>
                <div class="prob-row-sub" v-if="emp.current_employment.actual_regularization_date">
                  {{ formatDate(emp.current_employment.actual_regularization_date) }} 转正
                </div>
              </template>
              <template v-else-if="(emp.lifecycle_stage === 'SEPARATING' || emp.lifecycle_stage === 'SEPARATED') && emp.current_employment">
                <div class="prob-row">{{ formatDate(emp.current_employment.actual_hire_date || emp.current_employment.hire_date) }} 入职</div>
                <div class="prob-row-sub" v-if="emp.current_employment.actual_separation_date">
                  {{ formatDate(emp.current_employment.actual_separation_date) }} 离职
                </div>
              </template>
              <template v-else>
                <span class="text-muted">—</span>
              </template>
            </td>

            <!-- 4. 状态与风险列 -->
            <td class="td-status-risk">
              <div class="status-risk-cell">
                <LifecycleBadge :status="emp.lifecycle_stage" size="sm" />
                <RiskBadge v-if="emp.risk?.level" :level="emp.risk.level" size="sm" />
              </div>
            </td>

            <!-- 5. 接下来列 -->
            <td class="td-next">
              <template v-if="emp.next_action">
                <div class="next-text" :title="emp.next_action.title">
                  {{ emp.next_action.title }}
                </div>
                <div v-if="emp.next_action.overdue_days > 0" class="next-date overdue">
                  已逾期 {{ emp.next_action.overdue_days }} 天
                </div>
                <div v-else-if="emp.next_action.days_until_due === 0" class="next-date today">
                  今天到期
                </div>
                <div v-else-if="emp.next_action.days_until_due === 1" class="next-date">
                  明天到期
                </div>
                <div v-else-if="emp.next_action.days_until_due && emp.next_action.days_until_due > 1" class="next-date">
                  {{ shortDate(emp.next_action.due_at) }} · {{ emp.next_action.days_until_due }}天后
                </div>
                <div v-else-if="emp.next_action.due_at" class="next-date">
                  {{ shortDate(emp.next_action.due_at) }}
                </div>
              </template>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- 6. 操作列 -->
            <td class="td-actions" @click.stop>
              <div class="action-group">
                <button class="action-link" @click="goToDetail(emp)">查看</button>
                <div class="dropdown-wrap">
                  <button class="action-icon-btn" @click.stop="toggleMenu(emp.id)">
                    <MoreHorizontal :size="16" />
                  </button>
                  <div v-if="openMenuId === emp.id" class="dropdown-menu" @click.stop>
                    <button class="dropdown-item" @click="goToDetail(emp)">编辑员工</button>
                    <button class="dropdown-item" @click="goToDetail(emp)">查看档案</button>
                    <button class="dropdown-item" @click="goToDetail(emp)">记录沟通</button>
                    <button
                      v-if="emp.lifecycle_stage !== 'SEPARATED'"
                      class="dropdown-item"
                      @click="goToDetail(emp)"
                    >
                      发起异动
                    </button>
                    <button
                      v-if="emp.lifecycle_stage !== 'SEPARATED'"
                      class="dropdown-item"
                      @click="goToDetail(emp)"
                    >
                      办理离职
                    </button>
                    <div class="dropdown-divider" />
                    <button class="dropdown-item dropdown-danger" @click="confirmDelete(emp)">
                      删除员工
                    </button>
                  </div>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页栏 -->
    <div v-if="total > 0" class="pagination-bar">
      <div class="pagination-info text-sm text-tertiary">
        共 {{ total }} 名员工
      </div>
      <div class="pagination-controls">
        <button
          class="page-btn"
          :disabled="page <= 1"
          @click="goToPage(page - 1)"
        >
          上一页
        </button>
        <template v-for="p in totalPages" :key="p">
          <button
            v-if="p === 1 || p === totalPages || Math.abs(p - page) <= 2"
            class="page-btn page-num"
            :class="{ active: p === page }"
            @click="goToPage(p)"
          >
            {{ p }}
          </button>
          <span
            v-else-if="p === page - 3 || p === page + 3"
            class="page-ellipsis"
          >…</span>
        </template>
        <button
          class="page-btn"
          :disabled="page >= totalPages"
          @click="goToPage(page + 1)"
        >
          下一页
        </button>
        <select v-model="pageSize" class="page-size-select" @change="goToPage(1)">
          <option :value="10">10条/页</option>
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
        </select>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
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
/* ===== 页面布局 ===== */
.page-intro {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 20px;
}
.page-intro h1 {
  flex: 0 0 auto;
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
}
.page-intro p {
  flex: 1 1 auto;
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}
.page-actions {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  transition: all 0.15s;
}
.action-btn.primary {
  background: var(--color-primary, #4F46E5);
  color: #fff;
  border-color: var(--color-primary);
}
.action-btn:hover {
  border-color: var(--color-primary);
}
.action-btn.primary:hover {
  opacity: 0.92;
}

/* ===== 错误状态 ===== */
.error-card {
  padding: 40px;
  text-align: center;
}
.error-message p {
  margin: 0 0 16px;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

/* ===== 表格容器 ===== */
.table-wrapper {
  overflow: visible;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
th, td {
  padding: 11px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  line-height: 1.5;
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
  padding-top: 10px;
  padding-bottom: 10px;
}

/* 列宽 */
.col-employee { width: 180px; }
.col-employment { width: 180px; }
.col-probation { width: 220px; }
.col-status { width: 130px; }
.col-next { width: 160px; }
.col-actions { width: 100px; }

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
.td-employee {
  vertical-align: middle;
}
.emp-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.emp-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.emp-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.emp-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  overflow: hidden;
}
.emp-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.emp-age {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
}

/* hover 浮层 */
.hover-trigger {
  position: relative;
}
.emp-hover-card {
  display: none;
  position: absolute;
  left: 0;
  top: 100%;
  margin-top: 6px;
  z-index: 200;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-popover);
  padding: 10px 12px;
  min-width: 220px;
  white-space: nowrap;
}
.hover-trigger:hover .emp-hover-card {
  display: block;
}
.emp-hover-card::before {
  content: '';
  position: absolute;
  top: -5px;
  left: 24px;
  width: 8px;
  height: 8px;
  background: var(--color-surface, #fff);
  border-left: 1px solid var(--color-border);
  border-top: 1px solid var(--color-border);
  transform: rotate(45deg);
}
.hover-card-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0;
  font-size: var(--font-size-sm);
  line-height: 1.5;
}
.hover-card-item + .hover-card-item {
  border-top: 1px solid var(--color-border);
  margin-top: 2px;
  padding-top: 5px;
}
.hover-card-label {
  flex-shrink: 0;
  color: var(--color-text-tertiary);
  min-width: 56px;
}
.hover-card-value {
  color: var(--color-text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 2. 任职信息列 ===== */
.td-employment {
  vertical-align: middle;
}
.emp-dept-pos {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.emp-status-tag {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.emp-team {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 1px;
}

/* ===== 3. 入职与试用列 ===== */
.td-probation {
  vertical-align: middle;
}
.prob-row {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.4;
}
.prob-row-sub {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  margin-top: 1px;
}
.overdue-text {
  font-size: var(--font-size-xs);
  color: var(--color-danger);
  font-weight: 500;
  margin-top: 2px;
}

/* 试用期进度条 */
.prob-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.prob-bar-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--color-primary);
  min-width: 32px;
  text-align: right;
  flex-shrink: 0;
}
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

/* ===== 4. 状态与风险列 ===== */
.td-status-risk {
  vertical-align: middle;
}
.status-risk-cell {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

/* ===== 5. 接下来列 ===== */
.td-next {
  vertical-align: middle;
}
.next-text {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.next-date {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.next-date.overdue {
  color: var(--color-danger);
  font-weight: 500;
}
.next-date.today {
  color: var(--color-warning);
  font-weight: 500;
}

/* ===== 6. 操作列 ===== */
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
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.12s;
}
.action-link:hover {
  background: var(--color-primary-soft);
}
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
.action-icon-btn:hover {
  background: var(--color-bg);
  color: var(--color-text-secondary);
}
.dropdown-wrap {
  position: relative;
  display: inline-block;
}
.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 4px;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: var(--shadow-popover);
  min-width: 140px;
  z-index: 100;
  padding: 4px;
}
.dropdown-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
  border-radius: 4px;
}
.dropdown-item:hover {
  background: var(--color-bg);
}
.dropdown-danger {
  color: var(--color-danger) !important;
}
.dropdown-divider {
  height: 1px;
  background: var(--color-border);
  margin: 4px 0;
}

/* ===== 分页 ===== */
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding: 8px 0;
}
.pagination-info {
  font-size: var(--font-size-sm);
}
.pagination-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
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
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.page-btn.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.page-num {
  min-width: 32px;
  text-align: center;
  padding: 5px 8px;
}
.page-ellipsis {
  padding: 0 4px;
  color: var(--color-text-tertiary);
}
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
.text-muted {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}
.text-sm { font-size: var(--font-size-sm); }
.text-xs { font-size: var(--font-size-xs); }
.text-tertiary { color: var(--color-text-tertiary); }

/* ===== 骨架屏 ===== */
.table-skeleton {
  padding: 0 16px;
}
.skeleton-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}
.skeleton-row:last-child {
  border-bottom: none;
}
.skeleton-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.skeleton-cell-employee {
  flex: 0 0 180px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
}
.skeleton-cell-actions {
  flex: 0 0 100px;
  display: flex;
  align-items: center;
}
.skeleton-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-border);
  animation: shimmer 1.5s infinite;
}
.skeleton-lines {
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
  .col-employee { width: 160px; }
  .col-employment { width: 160px; }
  .col-probation { width: 200px; }
  .col-status { width: 120px; }
  .col-next { width: 140px; }
}
</style>
