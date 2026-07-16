<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchWorkItems, completeWorkItem, type WorkItem } from '@/services/workItemService'
import { useToast } from '@/composables/useToast'
import { formatDate, formatRelativeDate } from '@/utils/date'
import BaseBadge from '@/components/base/BaseBadge.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'

const router = useRouter()
const { showToast } = useToast()
const items = ref<WorkItem[]>([])
const loading = ref(true)
const activeTab = ref('all')
const completing = ref<Set<string>>(new Set())

const groupedItems = computed(() => {
  const overdue = items.value.filter((i) => i.overdue_days > 0 && i.status !== 'COMPLETED')
  const today = items.value.filter((i) => i.overdue_days === 0 && i.status === 'PENDING')
  const future = items.value.filter((i) => i.overdue_days < 0 && i.status === 'PENDING')
  const completed = items.value.filter((i) => i.status === 'COMPLETED')

  return { overdue, today, future, completed }
})

const counts = computed(() => ({
  all: items.value.length,
  overdue: groupedItems.value.overdue.length,
  today: groupedItems.value.today.length,
  future: groupedItems.value.future.length,
  completed: groupedItems.value.completed.length,
}))

async function loadItems() {
  loading.value = true
  try {
    items.value = await fetchWorkItems()
  } catch (e: any) {
    console.error('加载工作事项失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleComplete(item: WorkItem) {
  if (completing.value.has(item.id)) return
  completing.value.add(item.id)
  try {
    await completeWorkItem(item)
    showToast({ message: '事项已完成', type: 'success' })
    items.value = items.value.filter((i) => i.id !== item.id)
  } catch (e: any) {
    showToast({ message: e.message || '操作失败', type: 'error' })
  } finally {
    completing.value.delete(item.id)
  }
}

onMounted(loadItems)
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">工作事项</h1>
      <p class="page-subtitle">集中处理跟进、待办和员工关键节点</p>
    </div>

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
                <span v-if="item.employee_name">{{ item.employee_name }}</span>
                <span v-if="item.department"> · {{ item.department }}</span>
              </div>
            </div>
            <div class="item-actions">
              <RiskBadge v-if="item.risk_level && item.risk_level !== 'NONE'" :level="item.risk_level" size="sm" />
              <button class="complete-btn" :disabled="completing.has(item.id)" @click="handleComplete(item)">
                {{ completing.has(item.id) ? '...' : '完成' }}
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
                <span v-if="item.employee_name">{{ item.employee_name }}</span>
                <span v-if="item.department"> · {{ item.department }}</span>
              </div>
            </div>
            <div class="item-actions">
              <button class="complete-btn" :disabled="completing.has(item.id)" @click="handleComplete(item)">
                {{ completing.has(item.id) ? '...' : '完成' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Future -->
      <div v-if="groupedItems.future.length > 0 && (activeTab === 'all' || activeTab === 'future')" class="work-group">
        <div class="group-header">
          <span class="group-label">未来 7 天</span>
          <span class="group-count">{{ groupedItems.future.length }}</span>
        </div>
        <div class="group-items">
          <div v-for="item in groupedItems.future" :key="item.id" class="group-item">
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <span v-if="item.employee_name">{{ item.employee_name }}</span>
                <span v-if="item.department"> · {{ item.department }}</span>
                <span v-if="item.due_at"> · {{ formatDate(item.due_at) }}</span>
              </div>
            </div>
            <div class="item-actions">
              <button class="complete-btn" :disabled="completing.has(item.id)" @click="handleComplete(item)">
                {{ completing.has(item.id) ? '...' : '完成' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Completed -->
      <div v-if="groupedItems.completed.length > 0 && activeTab === 'completed'" class="work-group">
        <div class="group-header">
          <span class="group-label">已完成</span>
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
.page-intro {
  margin-bottom: 20px;
}

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
.complete-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 500;
  cursor: pointer;
}
.complete-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
.complete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
