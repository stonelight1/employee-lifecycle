<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchWorkItems,
  completeWorkItem,
  startFollowupTask,
  confirmFollowupTask,
} from '@/services/workItemService'
import type { WorkItem } from '@/types/work-item'
import { useToast } from '@/composables/useToast'
import { formatDate } from '@/utils/date'
import RiskBadge from '@/components/business/RiskBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import dayjs from 'dayjs'

const router = useRouter()
const { showToast } = useToast()
const items = ref<WorkItem[]>([])
const loading = ref(true)
const errorMessage = ref('')
const activeTab = ref('all')
const actionLoading = ref<Set<string>>(new Set())

/**
 * 按 days_until_due 分组：
 *   days_until_due < 0 → 已逾期
 *   days_until_due === 0 → 今天
 *   1 ≤ days_until_due ≤ 7 → 未来 7 天
 *   days_until_due > 7 → 更晚
 *   null → 无日期
 */
const groupedItems = computed(() => {
  const overdue: WorkItem[] = []
  const today: WorkItem[] = []
  const future7d: WorkItem[] = []
  const later: WorkItem[] = []
  const noDate: WorkItem[] = []
  const completed: WorkItem[] = []

  for (const item of items.value) {
    if (item.status === 'COMPLETED' || item.status === 'CANCELLED') {
      completed.push(item)
      continue
    }
    const d = item.days_until_due
    if (d === null || d === undefined) {
      noDate.push(item)
    } else if (d < 0) {
      overdue.push(item)
    } else if (d === 0) {
      today.push(item)
    } else if (d <= 7) {
      future7d.push(item)
    } else {
      later.push(item)
    }
  }

  return { overdue, today, future7d, later, noDate, completed }
})

const counts = computed(() => ({
  all: items.value.length,
  overdue: groupedItems.value.overdue.length,
  today: groupedItems.value.today.length,
  future: groupedItems.value.future7d.length,
  later: groupedItems.value.later.length,
  completed: groupedItems.value.completed.length,
}))

async function loadItems() {
  loading.value = true
  errorMessage.value = ''
  try {
    items.value = await fetchWorkItems()
  } catch (e: any) {
    console.error('加载工作事项失败:', e)
    errorMessage.value = e.message || '工作事项加载失败'
  } finally {
    loading.value = false
  }
}

/**
 * 根据状态处理操作按钮
 */
function getActionLabel(status: string): string {
  switch (status) {
    case 'PENDING': return '开始处理'
    case 'IN_PROGRESS': return '提交确认'
    case 'PENDING_CONFIRMATION': return '确认完成'
    default: return ''
  }
}

async function handleAction(item: WorkItem) {
  if (actionLoading.value.has(item.id)) return
  actionLoading.value.add(item.id)

  try {
    if (item.source_type === 'TODO') {
      // 待办：调用完成接口
      await completeWorkItem(item)
      showToast({ message: '待办已完成', type: 'success' })
      items.value = items.value.filter((i) => i.id !== item.id)
    } else {
      // 跟进任务状态处理
      switch (item.status) {
        case 'PENDING': {
          await startFollowupTask(item.source_id)
          // 刷新任务状态
          updateItemStatus(item.id, 'IN_PROGRESS')
          showToast({ message: '已开始处理', type: 'success', duration: 2000 })
          break
        }
        case 'IN_PROGRESS': {
          await completeWorkItem(item) // 调用 /submit
          updateItemStatus(item.id, 'PENDING_CONFIRMATION')
          showToast({ message: '已提交，等待确认', type: 'success', duration: 2000 })
          break
        }
        case 'PENDING_CONFIRMATION': {
          await confirmFollowupTask(item.source_id)
          showToast({ message: '事项已完成', type: 'success' })
          // COMPLETED 状态的活动事项应移除
          items.value = items.value.filter((i) => i.id !== item.id)
          break
        }
      }
    }
  } catch (e: any) {
    showToast({ message: e.message || '操作失败', type: 'error' })
  } finally {
    actionLoading.value.delete(item.id)
  }
}

function updateItemStatus(id: string, newStatus: WorkItem['status']) {
  const item = items.value.find((i) => i.id === id)
  if (item) {
    item.status = newStatus
  }
}

onMounted(loadItems)
</script>

<template>
  <div class="page">
    <PageHeader title="工作事项" subtitle="集中处理跟进、待办和员工关键节点" />

    <!-- Tabs -->
    <div class="tabs-bar">
      <button
        v-for="tab in ['all', 'overdue', 'today', 'future', 'completed']"
        :key="tab"
        class="tab-btn"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >
        {{ { all: '全部', overdue: '已逾期', today: '今天', future: '未来7天', completed: '已完成' }[tab] }}
        <span class="tab-count">{{ counts[tab as keyof typeof counts] }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <div v-else-if="errorMessage" class="error-state">
      <p>{{ errorMessage }}</p>
      <button class="action-btn" @click="loadItems">重新加载</button>
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0">
      <BaseEmpty title="当前没有待处理事项" description="新的跟进任务和系统待办会显示在这里" action-label="查看全部员工" @action="router.push('/employees')" />
    </div>

    <!-- Grouped items -->
    <div v-else class="work-groups">
      <!-- Overdue -->
      <div v-if="groupedItems.overdue.length > 0 && (activeTab === 'all' || activeTab === 'overdue')" class="work-group">
        <div class="group-header group-overdue">
          <span class="group-label">已逾期</span>
          <span class="group-count">{{ groupedItems.overdue.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.overdue" :key="item.id" class="group-item is-overdue">
            <div class="item-main">
              <div class="item-title">
                <span class="overdue-badge">逾期 {{ item.overdue_days }} 天</span>
                {{ item.title }}
              </div>
              <div class="item-meta">
                <template v-if="item.employee_name">
                  {{ item.employee_name }}<template v-if="item.department"> · {{ item.department }}</template>
                </template>
              </div>
            </div>
            <div class="item-actions">
              <RiskBadge v-if="item.risk_level && item.risk_level !== 'NONE'" :level="item.risk_level" size="sm" />
              <button
                v-if="getActionLabel(item.status)"
                class="action-btn"
                :disabled="actionLoading.has(item.id)"
                @click="handleAction(item)"
              >
                {{ actionLoading.has(item.id) ? '处理中...' : getActionLabel(item.status) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Today -->
      <div v-if="groupedItems.today.length > 0 && (activeTab === 'all' || activeTab === 'today')" class="work-group">
        <div class="group-header">
          <span class="group-label">今天</span>
          <span class="group-count">{{ groupedItems.today.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.today" :key="item.id" class="group-item">
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <template v-if="item.employee_name">
                  {{ item.employee_name }}<template v-if="item.department"> · {{ item.department }}</template>
                </template>
              </div>
            </div>
            <div class="item-actions">
              <button
                v-if="getActionLabel(item.status)"
                class="action-btn"
                :disabled="actionLoading.has(item.id)"
                @click="handleAction(item)"
              >
                {{ actionLoading.has(item.id) ? '处理中...' : getActionLabel(item.status) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Future 7 days -->
      <div v-if="groupedItems.future7d.length > 0 && (activeTab === 'all' || activeTab === 'future')" class="work-group">
        <div class="group-header">
          <span class="group-label">未来 7 天</span>
          <span class="group-count">{{ groupedItems.future7d.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.future7d" :key="item.id" class="group-item">
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <template v-if="item.employee_name">
                  {{ item.employee_name }}<template v-if="item.department"> · {{ item.department }}</template>
                </template>
                <template v-if="item.due_at"> · {{ formatDate(item.due_at) }}</template>
              </div>
            </div>
            <div class="item-actions">
              <button
                v-if="getActionLabel(item.status)"
                class="action-btn"
                :disabled="actionLoading.has(item.id)"
                @click="handleAction(item)"
              >
                {{ actionLoading.has(item.id) ? '处理中...' : getActionLabel(item.status) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Later -->
      <div v-if="groupedItems.later.length > 0 && (activeTab === 'all' || activeTab === 'future')" class="work-group">
        <div class="group-header">
          <span class="group-label">更晚</span>
          <span class="group-count">{{ groupedItems.later.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.later" :key="item.id" class="group-item">
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <template v-if="item.employee_name">
                  {{ item.employee_name }}<template v-if="item.department"> · {{ item.department }}</template>
                </template>
                <template v-if="item.due_at"> · {{ formatDate(item.due_at) }}</template>
              </div>
            </div>
            <div class="item-actions">
              <button
                v-if="getActionLabel(item.status)"
                class="action-btn"
                :disabled="actionLoading.has(item.id)"
                @click="handleAction(item)"
              >
                {{ actionLoading.has(item.id) ? '处理中...' : getActionLabel(item.status) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Completed -->
      <div v-if="groupedItems.completed.length > 0 && activeTab === 'completed'" class="work-group">
        <div class="group-header">
          <span class="group-label">已完成 / 已取消</span>
          <span class="group-count">{{ groupedItems.completed.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.completed" :key="item.id" class="group-item completed">
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

.tabs-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: var(--color-surface);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.tab-btn.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.tab-count {
  font-size: var(--font-size-xs);
  background: var(--color-bg);
  padding: 0 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}
.tab-btn.active .tab-count {
  background: rgba(255,255,255,0.2);
}

.work-groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.work-group {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}
.group-header.group-overdue {
  background: var(--color-danger-soft);
}
.group-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.group-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.group-items {
  padding: 4px 0;
}
.group-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
}
.group-item:last-child {
  border-bottom: none;
}
.group-item.is-overdue {
  border-left: 3px solid var(--color-danger);
}
.group-item.completed {
  opacity: 0.5;
}

.item-main {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}
.overdue-badge {
  font-size: var(--font-size-xs);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.item-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
.item-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-left: 16px;
}
.action-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.action-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-state {
  padding: 24px;
  text-align: center;
  color: var(--color-danger);
}
.error-state .action-btn {
  margin-top: 12px;
}
</style>
