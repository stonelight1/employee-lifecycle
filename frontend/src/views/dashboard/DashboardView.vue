<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDashboard, type DashboardData } from '@/services/dashboardService'
import { lifecycleStageMap, getStatusLabel } from '@/constants/status'
import { formatDate } from '@/utils/date'
import BaseSkeleton from '@/components/base/BaseSkeleton.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import RiskBadge from '@/components/business/RiskBadge.vue'

const router = useRouter()
const data = ref<DashboardData | null>(null)
const loading = ref(true)
const error = ref(false)
const apiConnected = ref(true)

const isEmpty = computed(() => {
  if (!data.value) return true
  return (
    data.value.metrics.active_employee_count === 0 &&
    data.value.metrics.probation_employee_count === 0 &&
    data.value.metrics.overdue_work_item_count === 0
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
  try {
    data.value = await fetchDashboard()
    apiConnected.value = true
  } catch (e: any) {
    console.error('加载工作台失败:', e)
    apiConnected.value = false
    error.value = true
  } finally {
    loading.value = false
  }
}

function goToEmployees(stage?: string) {
  const query = stage ? `?stage=${stage}` : ''
  router.push(`/employees${query}`)
}

function goToWorkItems() {
  router.push('/work-items')
}

onMounted(loadDashboard)
</script>

<template>
  <div class="dashboard">
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
    <div v-else-if="!apiConnected" class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">未能连接到后端服务</h1>
        <p class="welcome-subtitle">请确认后端 API 服务已启动 (端口 8013)</p>
        <div class="welcome-actions">
          <button class="action-btn primary" @click="loadDashboard">重新连接</button>
          <button class="action-btn secondary" @click="router.push('/employees')">前往员工中心</button>
        </div>
      </div>
    </div>

    <!-- 欢迎区（有数据或无数据） -->
    <div v-else-if="data" class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">
          <template v-if="!isEmpty">
            早上好，今天有 <strong>{{ welcomeText }}</strong>
          </template>
          <template v-else>
            欢迎使用员工生命周期管理系统
          </template>
        </h1>
        <p v-if="isEmpty" class="welcome-subtitle">开始使用：创建一个员工档案，系统将自动管理从入职到离职的全流程。</p>
        <div class="welcome-actions">
          <button class="action-btn primary" @click="router.push('/employees/new')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            新增员工
          </button>
          <button v-if="!isEmpty" class="action-btn secondary" @click="goToWorkItems()">
            查看全部事项
          </button>
        </div>
      </div>
    </div>

    <!-- 有数据时展示指标 -->
    <template v-if="data && !isEmpty">
      <!-- 指标卡 -->
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
        <!-- 左侧 -->
        <div class="column-left">
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
                </div>
                <div class="work-item-right">
                  <RiskBadge v-if="item.risk_level && item.risk_level !== 'NONE'" :level="item.risk_level" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧 -->
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
    <div v-else-if="data && isEmpty && apiConnected" class="empty-welcome">
      <div class="empty-welcome-card">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="empty-icon">
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>
        </svg>
        <h2 class="text-lg" style="font-weight: 600; margin-bottom: 8px;">开始搭建您的员工体系</h2>
        <p class="text-secondary text-sm" style="margin-bottom: 24px; max-width: 400px;">
          点击下方按钮创建第一个员工档案，系统将自动管理入职、试用期、转正、异动和离职的全生命周期。
        </p>
        <div class="quick-actions">
          <div class="quick-action-card" @click="router.push('/employees/new')">
            <div class="qa-icon">+</div>
            <div class="qa-text">
              <div class="qa-title">新增员工</div>
              <div class="qa-desc">创建员工基本信息档案</div>
            </div>
          </div>
          <div class="quick-action-card" @click="router.push('/employees')">
            <div class="qa-icon">👥</div>
            <div class="qa-text">
              <div class="qa-title">员工中心</div>
              <div class="qa-desc">查看和管理所有员工</div>
            </div>
          </div>
          <div class="quick-action-card" @click="router.push('/followup-nodes')">
            <div class="qa-icon">⚙</div>
            <div class="qa-text">
              <div class="qa-title">节点配置</div>
              <div class="qa-desc">配置跟进节点和流程</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
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
  gap: 6px;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
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

/* Empty welcome */
.empty-welcome {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}
.empty-welcome-card {
  text-align: center;
  max-width: 480px;
}
.empty-icon {
  color: var(--color-text-tertiary);
  margin-bottom: 16px;
  opacity: 0.5;
}
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.quick-action-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}
.quick-action-card:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.qa-icon {
  width: 40px;
  height: 40px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.qa-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.qa-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
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
</style>
