<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate } from '@/utils/date'
import { resolveLifecycleStage } from '@/utils/lifecycle'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(true)

interface RegularizationCandidate {
  employee_id: number
  employee_name: string
  employment_id: number
  department: string
  position: string
  hire_date: string
  probation_end_date: string
  lifecycle_stage: string
  overdue_days: number
}

const allCandidates = ref<RegularizationCandidate[]>([])

const groups = computed(() => {
  const overdue: RegularizationCandidate[] = []
  const dueSoon: RegularizationCandidate[] = []
  const dueLater: RegularizationCandidate[] = []
  const completed: RegularizationCandidate[] = []

  for (const c of allCandidates.value) {
    if (c.lifecycle_stage === 'REGULARIZATION_PENDING' && c.overdue_days > 0) {
      overdue.push(c)
    } else if (c.lifecycle_stage === 'REGULARIZATION_PENDING' && c.overdue_days === 0) {
      dueSoon.push(c)
    } else if (c.lifecycle_stage === 'REGULARIZATION_PENDING' && c.overdue_days < 0) {
      dueLater.push(c)
    } else if (c.lifecycle_stage === 'ACTIVE') {
      completed.push(c)
    }
  }

  return { overdue, dueSoon, dueLater, completed }
})

async function loadRegularizationCandidates() {
  loading.value = true
  try {
    // 获取所有员工（包含任职信息）
    const res = await get<{ items: any[]; total: number }>('/employees', {
      page: 1,
      page_size: 100,
      include_employment: true,
    })
    if (res.success && res.data) {
      const now = dayjs()
      const items: RegularizationCandidate[] = []

      for (const emp of res.data.items) {
        const ce = emp.current_employment
        if (!ce || !ce.probation_end_date) continue

        const stage = resolveLifecycleStage(ce, emp.employee_status)
        const endDate = dayjs(ce.probation_end_date)

        // 只包含待转正和已转正员工
        if (stage !== 'REGULARIZATION_PENDING' && stage !== 'ACTIVE') continue

        const overdue = endDate.isBefore(now, 'day') ? now.diff(endDate, 'day') : 0
        const daysUntil = endDate.diff(now, 'day')

        items.push({
          employee_id: emp.id,
          employee_name: emp.name,
          employment_id: ce.id,
          department: ce.department || '—',
          position: ce.position || '—',
          hire_date: ce.hire_date,
          probation_end_date: ce.probation_end_date,
          lifecycle_stage: stage,
          overdue_days: Math.max(0, overdue),
        })
      }

      allCandidates.value = items
    }
  } catch (e: any) {
    console.error('加载转正数据失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadRegularizationCandidates)
</script>

<template>
  <div class="page">
    <PageHeader title="转正管理" subtitle="查看即将转正、已超期和已完成转正的员工" />

    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <div v-else-if="allCandidates.length === 0">
      <BaseEmpty title="暂无转正相关数据" />
    </div>

    <div v-else class="regularization-sections">
      <!-- 已超期 -->
      <div v-if="groups.overdue.length > 0" class="section-card card">
        <div class="section-title" style="color: var(--color-danger);">已超过预计转正日期</div>
        <div class="emp-rows">
          <div v-for="c in groups.overdue" :key="c.employment_id" class="emp-row">
            <div>
              <span class="emp-row-name">{{ c.employee_name }}</span>
              <span class="text-sm text-tertiary">{{ c.department }} · {{ c.position }}</span>
            </div>
            <div class="emp-row-actions">
              <span class="text-sm text-danger">已超期 {{ c.overdue_days }} 天</span>
              <button class="row-btn" @click="router.push(`/employments/${c.employment_id}/regularization`)">处理转正</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 7天内待转正 -->
      <div v-if="groups.dueSoon.length > 0" class="section-card card">
        <div class="section-title">7 天内待转正</div>
        <div class="emp-rows">
          <div v-for="c in groups.dueSoon" :key="c.employment_id" class="emp-row">
            <div>
              <span class="emp-row-name">{{ c.employee_name }}</span>
              <span class="text-sm text-tertiary">{{ c.department }} · {{ c.position }}</span>
            </div>
            <div class="emp-row-actions">
              <span class="text-sm text-tertiary">预计 {{ formatDate(c.probation_end_date) }}</span>
              <button class="row-btn" @click="router.push(`/employments/${c.employment_id}/regularization`)">处理转正</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 更晚 -->
      <div v-if="groups.dueLater.length > 0" class="section-card card">
        <div class="section-title">30 天内待转正</div>
        <div class="emp-rows">
          <div v-for="c in groups.dueLater" :key="c.employment_id" class="emp-row">
            <div>
              <span class="emp-row-name">{{ c.employee_name }}</span>
              <span class="text-sm text-tertiary">{{ c.department }} · {{ c.position }}</span>
            </div>
            <div class="emp-row-actions">
              <span class="text-sm text-tertiary">预计 {{ formatDate(c.probation_end_date) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 已完成转正 -->
      <div v-if="groups.completed.length > 0" class="section-card card">
        <div class="section-title">已完成转正</div>
        <div class="emp-rows">
          <div v-for="c in groups.completed" :key="c.employment_id" class="emp-row">
            <div>
              <span class="emp-row-name">{{ c.employee_name }}</span>
              <span class="text-sm text-tertiary">{{ c.department }} · {{ c.position }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

.regularization-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-card {
  padding: 20px;
}
.section-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.emp-rows {
  display: flex;
  flex-direction: column;
}
.emp-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}
.emp-row:last-child {
  border-bottom: none;
}
.emp-row-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  display: block;
}
.emp-row-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.row-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.row-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
</style>
