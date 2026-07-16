<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDashboard } from '@/services/dashboardService'
import type { DashboardOverview } from '@/types/dashboard'
import { lifecycleStageMap, getStatusLabel } from '@/constants/status'
import { formatDate } from '@/utils/date'
import { getPendingCount } from '@/services/hrConfirmationService'
import BaseSkeleton from '@/components/base/BaseSkeleton.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'
import { AlertCircle, ClipboardList, Plus, Settings, Users } from 'lucide-vue-next'

const router = useRouter()
const data = ref<DashboardOverview | null>(null)
const loading = ref(true)
const error = ref(false)
const backendStatus = ref<'connected' | 'disconnected' | 'error'>('connected')
const errorMessage = ref('')
const pendingConfirmationCount = ref(0)

const isEmpty = computed(() => {
  if (!data.value) return true
  const metrics = data.value.metrics
  const hasMetricData = Object.values(metrics ?? {}).some((value) => Number(value) > 0)
  const hasListData =
    (data.value.lifecycle_distribution?.length ?? 0) > 0 ||
    (data.value.priority_work_items?.length ?? 0) > 0 ||
    (data.value.risk_employees?.length ?? 0) > 0 ||
    pendingConfirmationCount.value > 0
  return (
    !hasMetricData &&
    !hasListData
  )
})

const totalDistribution = computed(() => {
  if (!data.value?.lifecycle_distribution) return 0
  return data.value.lifecycle_distribution.reduce((sum, d) => sum + d.count, 0)
})

const welcomeText = computed(() => {
  if (!data.value) return ''
  const { metrics } = data.value
  const parts: string[] = []
  if (metrics.overdue_work_item_count > 0) {
    parts.push(`${metrics.overdue_work_item_count} 项逾期事项`)
  }
  if (metrics.regularization_due_7d_count > 0) {
    parts.push(`${metrics.regularization_due_7d_count} 名即将转正员工`)
  }
  if (parts.length === 0) return '暂无待处理事项，系统运行正常'
  return `${parts.join('和')}需要关注`
})

async function loadDashboard() {
  loading.value = true
  error.value = false
  backendStatus.value = 'connected'
  errorMessage.value = ''
  try {
    const [dashboardData, confirmData] = await Promise.allSettled([
      fetchDashboard(),
      getPendingCount(),
    ])
    if (dashboardData.status === 'fulfilled') {
      data.value = dashboardData.value
    } else {
      throw dashboardData.reason
    }
    if (confirmData.status === 'fulfilled') {
      pendingConfirmationCount.value = confirmData.value.pending_count
    }
    backendStatus.value = 'connected'
  } catch (e: any) {
    console.error('加载工作台失败:', e)
    if (e.message?.includes('后端连接失败')) {
      backendStatus.value = 'disconnected'
      errorMessage.value = '后端 API 连接失败，请确认服务已启动'
    } else {
      backendStatus.value = 'error'
      errorMessage.value = e.message || '未知错误'
    }
    error.value = true
  } finally {
    loading.value = false
  }
}

function goToEmployees(stage?: string) {
  const query: Record<string, string> = {}
  if (stage) query.lifecycle_stage = stage
  router.push({ path: '/employees', query })
}

function goToWorkItems() {
  router.push('/work-items')
}

onMounted(loadDashboard)
</script>

<template>
  <div
    class="dashboard"
    :class="{ 'dashboard--empty': data && isEmpty && backendStatus === 'connected' }"
  >
    <!-- Loading skeleton -->
    <div v-if="loading" class="dashboard-loading">
      <div class="metrics-grid">
        <div v-for="i in 4" :key="i" class="card">
          <BaseSkeleton :rows="2" />
        </div>
      </div>
      <div class="card" style="padding: 24px;">
        <BaseSkeleton :rows="6" type="table" />
      </div>
    </div>

    <!-- 后端未连接 -->
    <div v-else-if="backendStatus === 'disconnected'" class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">未能连接到后端服务</h1>
        <p class="welcome-subtitle">{{ errorMessage }}</p>
        <div class="welcome-actions">
          <button class="action-btn primary" @click="loadDashboard">重新连接</button>
          <button class="action-btn secondary" @click="router.push('/employees')">前往员工中心</button>
        </div>
      </div>
    </div>

    <!-- 后端错误 -->
    <div v-else-if="backendStatus === 'error' && !data" class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">加载工作台数据时出错</h1>
        <p class="welcome-subtitle">{{ errorMessage }}</p>
        <div class="welcome-actions">
          <button class="action-btn primary" @click="loadDashboard">重新加载</button>
        </div>
      </div>
    </div>

    <!-- 欢迎区 -->
    <div v-else-if="data && !isEmpty" class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">
          早上好，今天有 <strong>{{ welcomeText }}</strong>
        </h1>
        <div class="welcome-actions">
          <button class="action-btn secondary" @click="goToWorkItems()">
            查看全部事项
          </button>
        </div>
      </div>
    </div>

    <!-- 有数据时展示指标 -->
    <template v-if="data && !isEmpty">
      <div class="metrics-grid">
        <div class="metric-card" @click="goToEmployees()">
          <div class="metric-info">
            <div class="metric-value">{{ data.metrics.active_employee_count }}</div>
            <div class="metric-label">在职员工</div>
          </div>
          <div class="metric-icon icon-employees">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
          </div>
        </div>
        <div class="metric-card" @click="goToEmployees('PROBATION')">
          <div class="metric-info">
            <div class="metric-value">{{ data.metrics.probation_employee_count }}</div>
            <div class="metric-label">试用期员工</div>
          </div>
          <div class="metric-icon icon-probation">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
        </div>
        <div class="metric-card" @click="goToWorkItems()">
          <div class="metric-info">
            <div class="metric-value">{{ data.metrics.regularization_due_7d_count }}</div>
            <div class="metric-label">7天内待转正</div>
          </div>
          <div class="metric-icon icon-regularize">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="16 12 12 8 8 12"/><line x1="12" y1="16" x2="12" y2="8"/></svg>
          </div>
        </div>
        <div class="metric-card metric-overdue" @click="goToWorkItems()">
          <div class="metric-info">
            <div class="metric-value">{{ data.metrics.overdue_work_item_count }}</div>
            <div class="metric-label">已逾期事项</div>
          </div>
          <div class="metric-icon icon-overdue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
        </div>
      </div>

      <!-- 两栏布局 -->
      <div class="dashboard-columns">
        <div class="column-left">
          <!-- 待确认事项 -->
          <div v-if="pendingConfirmationCount > 0" class="section-card">
            <div class="section-card-header">
              <h3>
                待确认事项
                <span class="confirm-count-badge">{{ pendingConfirmationCount }}</span>
              </h3>
              <button class="header-link" @click="router.push('/hr-confirmations')">处理</button>
            </div>
            <div class="confirm-item-hint">
              <AlertCircle :size="16" class="confirm-icon" />
              <span>导入后仍有 {{ pendingConfirmationCount }} 条信息需要您确认</span>
            </div>
          </div>

          <div class="section-card">
            <div class="section-card-header">
              <h3>今日重点工作</h3>
              <button v-if="data.priority_work_items.length > 0" class="header-link" @click="goToWorkItems()">查看全部</button>
            </div>
            <div v-if="data.priority_work_items.length === 0" class="section-empty text-tertiary">
              当前没有待处理事项
            </div>
            <div v-else class="work-items-list">
              <div v-for="item in data.priority_work_items" :key="item.id" class="work-item-row" :class="{ 'is-overdue': item.overdue_days > 0 }">
                <div class="work-item-left">
                  <div class="work-item-title">
                    <span v-if="item.overdue_days > 0" class="overdue-tag">逾期{{ item.overdue_days }}天</span>
                    <span>{{ item.title }}</span>
                  </div>
                  <div v-if="item.employee_name" class="work-item-employee text-xs text-tertiary">
                    {{ item.employee_name }}{{ item.department ? ' · ' + item.department : '' }}
                  </div>
                </div>
                <div class="work-item-right">
                  <RiskBadge v-if="item.risk_level && item.risk_level !== 'NONE'" :level="item.risk_level" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="column-right">
          <div class="section-card">
            <div class="section-card-header">
              <h3>生命周期分布</h3>
            </div>
            <div v-if="data.lifecycle_distribution.length === 0" class="section-empty text-tertiary">
              暂无员工数据
            </div>
            <div v-else class="distribution-list">
              <div v-for="dist in data.lifecycle_distribution" :key="dist.stage" class="distribution-row" @click="goToEmployees(dist.stage)">
                <div class="dist-label">
                  <span class="dist-dot" :style="{ background: (lifecycleStageMap[dist.stage] || {}).color || '#98A2B3' }" />
                  <span class="text-sm">{{ (lifecycleStageMap[dist.stage] || {}).label || dist.stage }}</span>
                </div>
                <div class="dist-bar-wrap">
                  <div class="dist-bar" :style="{ width: totalDistribution > 0 ? (dist.count / totalDistribution * 100) + '%' : '0%', background: (lifecycleStageMap[dist.stage] || {}).color || '#98A2B3' }" />
                </div>
                <span class="dist-count">{{ dist.count }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 空数据欢迎页 -->
    <main v-else-if="data && isEmpty && backendStatus === 'connected'" class="dashboard-content">
      <section class="dashboard-empty" aria-labelledby="dashboard-empty-title">
        <div class="dashboard-empty__content">
          <p class="dashboard-empty__eyebrow">员工生命周期管理</p>
          <h1 id="dashboard-empty-title" class="dashboard-empty__title">开始搭建您的员工管理体系</h1>
          <p class="dashboard-empty__desc">
            创建员工档案后，系统将自动管理员工的入职、试用期、转正、异动和离职流程。
          </p>
          <RouterLink class="action-btn primary dashboard-empty__primary" to="/employees/new">
            <Plus :size="16" aria-hidden="true" />
            新增员工
          </RouterLink>

          <div class="dashboard-empty__shortcuts" aria-label="快捷入口">
            <RouterLink class="dashboard-empty__shortcut" to="/employees">
              <span class="dashboard-empty__shortcut-icon" aria-hidden="true">
                <Users :size="22" />
              </span>
              <span class="dashboard-empty__shortcut-title">员工中心</span>
              <span class="dashboard-empty__shortcut-desc">查看和管理员工档案</span>
            </RouterLink>
            <RouterLink class="dashboard-empty__shortcut" to="/followup-nodes">
              <span class="dashboard-empty__shortcut-icon" aria-hidden="true">
                <Settings :size="22" />
              </span>
              <span class="dashboard-empty__shortcut-title">节点配置</span>
              <span class="dashboard-empty__shortcut-desc">配置试用期跟进节点</span>
            </RouterLink>
            <RouterLink class="dashboard-empty__shortcut" to="/work-items">
              <span class="dashboard-empty__shortcut-icon" aria-hidden="true">
                <ClipboardList :size="22" />
              </span>
              <span class="dashboard-empty__shortcut-title">工作事项</span>
              <span class="dashboard-empty__shortcut-desc">查看当前需要处理的事项</span>
            </RouterLink>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  width: 100%;
  max-width: 1400px;
}
.dashboard--empty {
  max-width: none;
  width: calc(100vw - var(--sidebar-width) - 64px);
}

/* Welcome */
.welcome-section {
  margin-bottom: 24px;
}
.welcome-content {
  padding: 24px 0;
}
.welcome-title {
  font-size: 22px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
}
.welcome-title strong {
  color: var(--color-primary);
  font-weight: 600;
}
.welcome-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}
.welcome-actions {
  display: flex;
  gap: 10px;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
  text-decoration: none;
}
.action-btn.primary {
  background: var(--color-primary);
  color: #fff;
}
.action-btn.primary:hover {
  background: var(--color-primary-hover);
}
.action-btn.secondary {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.action-btn.secondary:hover {
  background: var(--color-bg);
}

/* Metrics */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.metric-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.metric-card:hover {
  box-shadow: var(--shadow-card);
}
.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1;
  margin-bottom: 4px;
}
.metric-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.icon-employees { background: var(--color-primary-soft); color: var(--color-primary); }
.icon-probation { background: #EFF6FF; color: #2563EB; }
.icon-regularize { background: var(--color-success-soft); color: var(--color-success); }
.icon-overdue { background: var(--color-danger-soft); color: var(--color-danger); }

/* Two columns */
.dashboard-columns {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 16px;
  align-items: start;
}

/* Section card */
.section-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
  overflow: hidden;
}
.section-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}
.section-card-header h3 {
  font-size: var(--font-size-base);
  font-weight: 600;
}
.header-link {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.section-empty {
  padding: 32px 20px;
  text-align: center;
  font-size: var(--font-size-sm);
}

/* Work items */
.work-items-list {
  padding: 4px 0;
}
.work-item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  transition: background 0.15s;
}
.work-item-row:hover {
  background: var(--color-bg);
}
.work-item-row.is-overdue {
  border-left: 3px solid var(--color-danger);
}
.confirm-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--color-danger);
  margin-left: 8px;
}
.confirm-item-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--color-warning-bg, #fffbeb);
  border-radius: 8px;
  color: var(--color-warning-text, #92400e);
  font-size: 14px;
}
.confirm-icon {
  flex-shrink: 0;
  color: var(--color-warning);
}
.work-item-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}
.overdue-tag {
  font-size: var(--font-size-xs);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}

/* Distribution */
.distribution-list {
  padding: 12px 20px;
}
.distribution-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  cursor: pointer;
}
.distribution-row:hover {
  opacity: 0.8;
}
.dist-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  width: 90px;
  flex-shrink: 0;
}
.dist-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dist-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--color-bg);
  border-radius: 99px;
  overflow: hidden;
}
.dist-bar {
  height: 100%;
  border-radius: 99px;
  transition: width 0.5s ease;
}
.dist-count {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  width: 24px;
  text-align: right;
}

/* Empty dashboard */
.dashboard-content {
  width: 100%;
}
.dashboard-empty {
  min-height: calc(100vh - var(--topbar-height) - 48px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: clamp(64px, 10vh, 120px) 32px 32px;
  box-sizing: border-box;
}
.dashboard-empty__content {
  width: 100%;
  max-width: 880px;
  text-align: center;
}
.dashboard-empty__eyebrow {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  margin: 0 0 12px;
}
.dashboard-empty__title {
  color: var(--color-text-primary);
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.25;
  margin: 0;
}
.dashboard-empty__desc {
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
  line-height: 1.7;
  max-width: 620px;
  margin: 16px auto 24px;
}
.dashboard-empty__primary {
  min-width: 132px;
  height: 40px;
}
.dashboard-empty__shortcuts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 40px;
}
.dashboard-empty__shortcut {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
  padding: 22px 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  text-align: center;
  text-decoration: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.dashboard-empty__shortcut:hover,
.dashboard-empty__shortcut:focus-visible {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-card);
  background: var(--color-surface-secondary);
  outline: none;
}
.dashboard-empty__shortcut-icon {
  width: 44px;
  height: 44px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}
.dashboard-empty__shortcut-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  line-height: 1.4;
}
.dashboard-empty__shortcut-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-top: 4px;
}

/* Loading */
.dashboard-loading {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1024px) {
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 1280px) {
  .dashboard--empty {
    width: calc(100vw - var(--sidebar-width) - 48px);
  }
  :global(.app-layout:has(.sidebar.collapsed) .dashboard--empty) {
    width: calc(100vw - var(--sidebar-collapsed-width) - 48px);
  }
}

@media (min-width: 1281px) {
  :global(.app-layout:has(.sidebar.collapsed) .dashboard--empty) {
    width: calc(100vw - var(--sidebar-collapsed-width) - 64px);
  }
}

@media (max-width: 1100px) {
  .dashboard-empty {
    padding: clamp(48px, 8vh, 80px) 16px 24px;
  }
  .dashboard-empty__shortcuts {
    grid-template-columns: 1fr;
    max-width: 560px;
    margin-left: auto;
    margin-right: auto;
  }
}
</style>
