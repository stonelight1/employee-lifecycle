<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate } from '@/utils/date'
import LifecycleBadge from '@/components/business/LifecycleBadge.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'

const router = useRouter()
const employees = ref<any[]>([])
const loading = ref(true)

const groups = ref({
  dueSoon: [] as any[],
  dueLater: [] as any[],
  overdue: [] as any[],
  completed: [] as any[],
})

async function loadRegularizationCandidates() {
  loading.value = true
  try {
    const res = await get<{ items: any[]; total: number }>('/employees', { page: 1, page_size: 100 })
    if (res.success && res.data) {
      const all = res.data.items
      const candidates: any[] = []
      for (const emp of all) {
        const empRes = await get<any>(`/employees/${emp.id}/employments`)
        const employments = empRes.data?.items || []
        for (const e of employments) {
          if (e.probation_end_date) {
            candidates.push({
              employee_id: emp.id,
              employee_name: emp.name,
              employment_id: e.id,
              department: e.department,
              position: e.position,
              hire_date: e.hire_date,
              probation_end_date: e.probation_end_date,
              employment_status: e.employment_status,
              employee_status: emp.employee_status,
            })
          }
        }
      }

      const now = new Date()
      groups.value = {
        dueSoon: candidates.filter((c) => {
          const end = new Date(c.probation_end_date)
          const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
          return diff <= 7 && diff >= 0
        }),
        dueLater: candidates.filter((c) => {
          const end = new Date(c.probation_end_date)
          const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
          return diff > 7 && diff <= 30
        }),
        overdue: candidates.filter((c) => {
          return new Date(c.probation_end_date) < now && c.employment_status !== 'REGULAR'
        }),
        completed: candidates.filter((c) => c.employment_status === 'REGULAR'),
      }
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
    <div class="page-intro">
      <h1 class="page-title">转正管理</h1>
      <p class="page-subtitle">查看即将转正、已超期和已完成转正的员工</p>
    </div>

    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <div v-else-if="!groups.dueSoon.length && !groups.overdue.length && !groups.dueLater.length && !groups.completed.length">
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
              <span class="text-sm text-danger">已超期</span>
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

      <!-- 30天内 -->
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

      <!-- 已完成 -->
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
.page-intro {
  margin-bottom: 20px;
}
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
