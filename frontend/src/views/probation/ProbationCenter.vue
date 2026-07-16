<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate } from '@/utils/date'
import RiskBadge from '@/components/business/RiskBadge.vue'
import ProbationProgress from '@/components/business/ProbationProgress.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'

const router = useRouter()
const employees = ref<any[]>([])
const loading = ref(true)

async function loadProbationEmployees() {
  loading.value = true
  try {
    const res = await get<{ items: any[]; total: number }>('/employees', {
      page: 1,
      page_size: 100,
    })
    if (res.success && res.data) {
      // Client-side filter for probation employees
      const all = res.data.items
      const probationers: any[] = []
      for (const emp of all) {
        const empRes = await get<any>(`/employees/${emp.id}`)
        if (empRes.success && empRes.data) {
          const empData = empRes.data
          // Load employment info
          const empListRes = await get<{ items: any[]; total: number }>(`/employees/${emp.id}/employments`)
          const employment = empListRes.data?.items?.[0]
          if (employment && (employment.employment_status === 'PROBATION' || emp.employee_status === 'PROBATION')) {
            probationers.push({
              id: emp.id,
              name: emp.name,
              employee_no: emp.employee_no,
              department: employment.department,
              position: employment.position,
              hire_date: employment.hire_date,
              probation_end_date: employment.probation_end_date,
              employment_id: employment.id,
            })
          }
        }
      }
      employees.value = probationers
    }
  } catch (e: any) {
    console.error('加载试用期员工失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadProbationEmployees)
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
        <div class="emp-card-header">
          <div class="emp-name">{{ emp.name }}</div>
          <div class="emp-dept">{{ emp.department }} · {{ emp.position }}</div>
        </div>

        <ProbationProgress
          :hire-date="emp.hire_date"
          :probation-end-date="emp.probation_end_date"
          size="sm"
        />

        <div class="emp-card-footer">
          <div class="emp-footer-info">
            <div class="text-xs text-tertiary">入职 {{ formatDate(emp.hire_date) }}</div>
          </div>
          <button class="card-btn" @click="router.push(`/employees/${emp.id}`)">查看档案</button>
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
  gap: 16px;
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
</style>
