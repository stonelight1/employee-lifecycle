<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { get, del } from '@/api'
import { formatDate, formatTenure, calculateProbationProgress } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseBadge from '@/components/base/BaseBadge.vue'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import ProbationProgress from '@/components/business/ProbationProgress.vue'
import EmployeeAvatar from '@/components/business/EmployeeAvatar.vue'
import EmployeeQuickDrawer from '@/components/business/EmployeeQuickDrawer.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'

interface EmployeeRow {
  id: number
  name: string
  employee_no?: string
  mobile?: string
  department?: string
  position?: string
  hire_date?: string
  employment_status?: string
  employee_status: string
  probation_end_date?: string
  next_action?: string
  employment_id?: number
  created_at: string
}

const router = useRouter()
const route = useRoute()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const employees = ref<EmployeeRow[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const searchName = ref('')
const filterStage = ref('')
const filterRisk = ref('')
const selectedEmployeeId = ref(0)
const showDrawer = ref(false)

// Parse URL params on mount
onMounted(() => {
  const stage = route.query.stage as string
  if (stage) filterStage.value = stage
  loadEmployees()
})

// Watch filter changes
watch([filterStage, filterRisk], () => {
  page.value = 1
  loadEmployees()
})

async function loadEmployees() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize,
    }
    if (searchName.value) params.name = searchName.value

    const res = await get<{ items: any[]; total: number }>('/employees', params)
    if (res.success && res.data) {
      // Enrich with employment data
      const rows: EmployeeRow[] = []
      for (const emp of res.data.items) {
        const row: EmployeeRow = {
          id: emp.id,
          name: emp.name,
          employee_no: emp.employee_no,
          mobile: emp.mobile,
          employee_status: emp.employee_status,
          created_at: emp.created_at,
        }

        try {
          const empListRes = await get<{ items: any[] }>(`/employees/${emp.id}/employments`)
          const employment = empListRes.data?.items?.[0]
          if (employment) {
            row.department = employment.department
            row.position = employment.position
            row.hire_date = employment.hire_date
            row.employment_status = employment.employment_status
            row.probation_end_date = employment.probation_end_date
            row.employment_id = employment.id
          }
        } catch {}

        rows.push(row)
      }
      employees.value = rows
      total.value = res.data.total
    }
  } catch (e: any) {
    console.error('加载员工列表失败:', e)
  } finally {
    loading.value = false
  }
}

function handleRowClick(emp: EmployeeRow) {
  selectedEmployeeId.value = emp.id
  showDrawer.value = true
}

function goToDetail(emp: EmployeeRow) {
  router.push(`/employees/${emp.id}`)
}

function confirmDelete(emp: EmployeeRow) {
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

const totalPages = computed(() => Math.ceil(total.value / pageSize))

// Filter tabs
const stageFilters = [
  { label: '全部', value: '' },
  { label: '试用期', value: 'PROBATION' },
  { label: '待转正', value: 'REGULARIZATION_PENDING' },
  { label: '正式在职', value: 'ACTIVE' },
  { label: '已离职', value: 'SEPARATED' },
]
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">员工中心</h1>
      <p class="page-subtitle">统一查看员工状态、试用期进度和下一步事项</p>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-bar">
      <div class="filter-tabs">
        <button
          v-for="f in stageFilters"
          :key="f.value"
          class="filter-tab"
          :class="{ active: filterStage === f.value }"
          @click="filterStage = f.value"
        >
          {{ f.label }}
        </button>
      </div>
      <div class="filter-actions">
        <input
          v-model="searchName"
          class="search-input"
          placeholder="搜索姓名、手机号"
          @input="loadEmployees()"
        />
      </div>
    </div>

    <!-- Table -->
    <div class="table-card card">
      <table v-if="employees.length > 0">
        <thead>
          <tr>
            <th>员工</th>
            <th>部门 / 岗位</th>
            <th>入职信息</th>
            <th>生命周期</th>
            <th>试用期</th>
            <th>风险</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="emp in employees" :key="emp.id" class="emp-row" @click="handleRowClick(emp)">
            <td class="td-employee">
              <EmployeeAvatar :name="emp.name" size="sm" />
              <div class="emp-name-info">
                <span class="emp-name-text">{{ emp.name }}</span>
                <span class="emp-no">{{ emp.employee_no || '—' }}</span>
              </div>
            </td>
            <td class="td-dept">
              <div class="dept-text">{{ emp.department || '—' }}</div>
              <div class="pos-text">{{ emp.position || '—' }}</div>
            </td>
            <td class="td-hire">
              <div>{{ formatDate(emp.hire_date) }}</div>
              <div class="text-xs text-tertiary">{{ formatTenure(emp.hire_date) }}</div>
            </td>
            <td>
              <LifecycleBadge :status="emp.employment_status || emp.employee_status" size="sm" />
            </td>
            <td class="td-probation">
              <ProbationProgress
                :hire-date="emp.hire_date"
                :probation-end-date="emp.probation_end_date"
                size="sm"
              />
            </td>
            <td>
              <RiskBadge level="NONE" size="sm" />
            </td>
            <td class="td-actions" @click.stop>
              <button class="action-link" @click="goToDetail(emp)">查看</button>
              <div class="more-menu">
                <button class="action-link danger" @click="confirmDelete(emp)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading">
        <BaseEmpty title="暂无员工数据" description="点击右上角按钮新增员工" action-label="新增员工" @action="router.push('/employees/new')" />
      </div>
      <div v-else class="loading-state text-tertiary">加载中...</div>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="pagination-bar">
      <div class="text-sm text-tertiary">共 {{ total }} 条</div>
      <div class="pagination-controls">
        <button :disabled="page <= 1" class="page-btn" @click="page--; loadEmployees()">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" class="page-btn" @click="page++; loadEmployees()">下一页</button>
      </div>
    </div>

    <!-- Drawer -->
    <EmployeeQuickDrawer :employee-id="selectedEmployeeId" :show="showDrawer" @close="showDrawer = false" />

    <!-- Delete confirm modal -->
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

<script lang="ts">
import BaseModal from '@/components/base/BaseModal.vue'
export default {}
</script>

<style scoped>
.page-intro {
  margin-bottom: 20px;
}

/* Filter bar */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.filter-tab {
  padding: 5px 14px;
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: var(--color-surface);
  font-size: var(--font-size-sm);
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
.filter-actions {
  display: flex;
  gap: 8px;
}
.search-input {
  padding: 7px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  width: 220px;
  font-size: var(--font-size-sm);
  outline: none;
}
.search-input:focus {
  border-color: var(--color-primary);
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
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
th {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-secondary);
}
.emp-row {
  cursor: pointer;
  transition: background 0.15s;
}
.emp-row:hover {
  background: var(--color-bg);
}

.td-employee {
  display: flex;
  align-items: center;
  gap: 10px;
}
.emp-name-text {
  font-weight: 500;
}
.emp-no {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.dept-text {
  font-weight: 500;
  margin-bottom: 2px;
}
.pos-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.td-probation {
  min-width: 140px;
}
.td-actions {
  white-space: nowrap;
}
.action-link {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 2px 8px;
}
.action-link.danger {
  color: var(--color-danger);
}
.more-menu {
  display: inline;
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
</style>
