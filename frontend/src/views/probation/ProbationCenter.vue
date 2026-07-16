<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate, calculateProbationProgress } from '@/utils/date'
import { getStatusLabel, followupStatusMap, riskMap } from '@/constants/status'
import RiskBadge from '@/components/business/RiskBadge.vue'
import ProbationProgress from '@/components/business/ProbationProgress.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import {
  ClipboardCheck,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-vue-next'
import dayjs from 'dayjs'

const router = useRouter()
const employees = ref<any[]>([])
const loading = ref(true)
const expandedId = ref<number | null>(null)

/**
 * 试用期员工接口返回结构
 */
interface ProbationEmployee {
  employee_id: number
  employee_name: string
  department: string
  position: string
  hire_date: string
  employment_id: number
  expected_regularization_date: string | null
  probation_progress: number
  risk_level: string
  followup_progress: {
    completed_count: number
    total_count: number
    completed_nodes: { task_id: number; node_name: string; completed_at: string | null }[]
    all_nodes: { task_id: number; node_name: string; planned_date: string | null; status: string; completed_at: string | null }[]
    next_node: {
      task_id: number | null
      node_name: string | null
      planned_date: string | null
      status: string
      days_until_due: number | null
      overdue_days: number
    } | null
  }
}

async function loadProbationEmployees() {
  loading.value = true
  try {
    const res = await get<{ items: any[]; total: number }>('/probation/employees', {
      page: 1,
      page_size: 100,
    })
    if (res.success && res.data) {
      employees.value = res.data.items.map((emp: any) => ({
        id: emp.employee_id,
        name: emp.employee_name,
        department: emp.department || '—',
        position: emp.position || '—',
        hire_date: emp.hire_date,
        employment_id: emp.employment_id,
        expected_regularization_date: emp.expected_regularization_date,
        progress: emp.probation_progress || 0,
        risk_level: emp.risk_level || 'NONE',
        followup_progress: emp.followup_progress || {
          completed_count: 0,
          total_count: 0,
          completed_nodes: [],
          all_nodes: [],
          next_node: null,
        },
      }))
    }
  } catch (e: any) {
    console.error('加载试用期员工失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadProbationEmployees)

/**
 * 获取跟进节点状态标签和颜色
 */
function getNodeStatusInfo(status: string): { label: string; className: string } {
  const map: Record<string, { label: string; className: string }> = {
    COMPLETED: { label: '已完成', className: 'node-completed' },
    PENDING: { label: '待处理', className: 'node-pending' },
    IN_PROGRESS: { label: '处理中', className: 'node-in-progress' },
    PENDING_CONFIRMATION: { label: '待确认', className: 'node-pending-confirmation' },
    CANCELLED: { label: '已取消', className: 'node-cancelled' },
    ALL_COMPLETED: { label: '已全部完成', className: 'node-completed' },
    NO_TASKS: { label: '尚未生成跟进节点', className: 'node-no-tasks' },
  }
  return map[status] || { label: status, className: '' }
}

/**
 * 处理跟进操作
 */
function handleFollowupAction(emp: any, task: any) {
  if (!task || !task.task_id) return
  const status = task.status

  if (status === 'PENDING') {
    router.push(`/followup-tasks/${task.task_id}`)
  } else if (status === 'IN_PROGRESS') {
    router.push(`/followup-tasks/${task.task_id}`)
  } else if (status === 'PENDING_CONFIRMATION') {
    router.push(`/followup-tasks/${task.task_id}`)
  }
}

function toggleExpand(empId: number) {
  expandedId.value = expandedId.value === empId ? null : empId
}
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">试用期中心</h1>
      <p class="page-subtitle">集中管理试用期员工、跟进节点和评估记录</p>
    </div>

    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <div v-else-if="employees.length === 0">
      <BaseEmpty title="当前没有试用期员工" description="新员工入职后将自动显示在这里" />
    </div>

    <div v-else class="employee-cards">
      <div v-for="emp in employees" :key="emp.id" class="emp-card card">
        <!-- Card header -->
        <div class="emp-card-header">
          <div class="emp-name">{{ emp.name }}</div>
          <div class="emp-dept">{{ emp.department }} · {{ emp.position }}</div>
        </div>

        <!-- Probation progress bar -->
        <ProbationProgress
          :hire-date="emp.hire_date"
          :probation-end-date="emp.expected_regularization_date"
          size="sm"
        />

        <!-- Overdue notice -->
        <div v-if="emp.followup_progress?.next_node?.overdue_days > 0" class="overdue-notice">
          已超期 {{ emp.followup_progress.next_node.overdue_days }} 天
        </div>

        <!-- Followup progress summary -->
        <div class="followup-section">
          <div class="followup-header">
            <ClipboardCheck :size="14" />
            <span class="followup-label">跟进进度</span>
            <span class="followup-count">
              {{ emp.followup_progress.completed_count }} / {{ emp.followup_progress.total_count }}
            </span>
          </div>

          <!-- Next node -->
          <div v-if="emp.followup_progress?.next_node" class="next-node-section">
            <template v-if="emp.followup_progress.next_node.status === 'ALL_COMPLETED'">
              <div class="next-node-text">跟进节点已全部完成</div>
            </template>
            <template v-else-if="emp.followup_progress.next_node.status === 'NO_TASKS'">
              <div class="next-node-text">尚未生成跟进节点</div>
            </template>
            <template v-else>
              <div class="next-node-info">
                <span class="next-node-label">下一节点：</span>
                <span class="next-node-name">{{ emp.followup_progress.next_node.node_name }}</span>
              </div>
              <div v-if="emp.followup_progress.next_node.planned_date" class="next-node-date">
                预计 {{ formatDate(emp.followup_progress.next_node.planned_date) }}
              </div>
              <div v-if="emp.followup_progress.next_node.overdue_days > 0" class="next-node-overdue">
                已逾期 {{ emp.followup_progress.next_node.overdue_days }} 天
              </div>
            </template>
          </div>

          <!-- Expand/collapse for all nodes -->
          <div
            v-if="emp.followup_progress?.all_nodes?.length > 0"
            class="expand-toggle"
            @click="toggleExpand(emp.id)"
          >
            {{ expandedId === emp.id ? '收起节点' : '查看全部节点' }}
            <component :is="expandedId === emp.id ? ChevronUp : ChevronDown" :size="14" />
          </div>

          <!-- All nodes (expanded) -->
          <div v-if="expandedId === emp.id && emp.followup_progress?.all_nodes?.length > 0" class="node-list">
            <div
              v-for="node in emp.followup_progress.all_nodes"
              :key="node.task_id"
              class="node-item"
              :class="getNodeStatusInfo(node.status).className"
            >
              <span class="node-status-icon">
                {{ node.status === 'COMPLETED' ? '✓' : node.status === 'CANCELLED' ? '✕' : '○' }}
              </span>
              <span class="node-name">{{ node.node_name }}</span>
              <span class="node-status">{{ getNodeStatusInfo(node.status).label }}</span>
            </div>
          </div>
        </div>

        <!-- Card footer -->
        <div class="emp-card-footer">
          <div class="emp-footer-info">
            <div class="text-xs text-tertiary">入职 {{ formatDate(emp.hire_date) }}</div>
          </div>
          <div class="emp-footer-actions">
            <RiskBadge :level="emp.risk_level" size="sm" />
            <button
              v-if="emp.followup_progress?.next_node?.task_id && emp.followup_progress.next_node.status !== 'ALL_COMPLETED' && emp.followup_progress.next_node.status !== 'NO_TASKS'"
              class="action-btn"
              @click="handleFollowupAction(emp, emp.followup_progress.next_node)"
            >
              立即处理
            </button>
            <button class="card-btn" @click="router.push(`/employees/${emp.id}`)">查看档案</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-intro {
  margin-bottom: 20px;
}

.employee-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.emp-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.emp-card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.emp-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}
.emp-dept {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.overdue-notice {
  font-size: var(--font-size-xs);
  color: var(--color-danger);
  background: var(--color-danger-soft);
  padding: 4px 8px;
  border-radius: 4px;
}

/* Followup section */
.followup-section {
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.followup-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
.followup-label {
  font-weight: 500;
}
.followup-count {
  margin-left: auto;
  font-weight: 600;
  color: var(--color-text-primary);
}

.next-node-section {
  font-size: var(--font-size-xs);
}
.next-node-text {
  color: var(--color-text-tertiary);
  padding: 4px 0;
}
.next-node-info {
  display: flex;
  gap: 4px;
  align-items: center;
}
.next-node-label {
  color: var(--color-text-tertiary);
}
.next-node-name {
  font-weight: 500;
  color: var(--color-text-primary);
}
.next-node-date {
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.next-node-overdue {
  color: var(--color-danger);
  font-weight: 500;
  margin-top: 2px;
}

.expand-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  cursor: pointer;
  margin-top: 8px;
}
.expand-toggle:hover {
  text-decoration: underline;
}

.node-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.node-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  padding: 3px 0;
}
.node-status-icon {
  width: 16px;
  text-align: center;
  font-weight: bold;
}
.node-name {
  flex: 1;
  color: var(--color-text-primary);
}
.node-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
}
.node-completed .node-status-icon { color: var(--color-success); }
.node-completed .node-status { color: var(--color-success); background: var(--color-success-soft); }
.node-pending .node-status-icon { color: var(--color-text-tertiary); }
.node-pending .node-status { color: var(--color-text-tertiary); background: var(--color-bg); }
.node-in-progress .node-status-icon { color: var(--color-primary); }
.node-in-progress .node-status { color: var(--color-primary); background: var(--color-primary-soft); }
.node-pending-confirmation .node-status-icon { color: var(--color-warning); }
.node-pending-confirmation .node-status { color: var(--color-warning); background: var(--color-warning-soft); }
.node-cancelled .node-status-icon { color: var(--color-text-tertiary); }
.node-cancelled .node-status { color: var(--color-text-tertiary); }

/* Footer */
.emp-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}
.emp-footer-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.emp-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.card-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
.action-btn {
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.action-btn:hover {
  background: var(--color-primary-hover);
}
</style>
