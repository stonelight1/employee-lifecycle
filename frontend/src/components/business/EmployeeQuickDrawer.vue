<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate, formatTenure } from '@/utils/date'
import EmployeeAvatar from './EmployeeAvatar.vue'
import LifecycleBadge from './LifecycleBadge.vue'
import RiskBadge from './RiskBadge.vue'
import ProbationProgress from './ProbationProgress.vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'

const props = withDefaults(defineProps<{
  employeeId?: number
  show?: boolean
}>(), {
  employeeId: 0,
  show: false,
})

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()
const employee = ref<any>(null)
const employment = ref<any>(null)
const loading = ref(false)

async function loadData() {
  if (!props.employeeId) return
  loading.value = true
  try {
    const empRes = await get<any>(`/employees/${props.employeeId}`)
    if (empRes.success) employee.value = empRes.data

    const empListRes = await get<{ items: any[] }>(`/employees/${props.employeeId}/employments`)
    if (empListRes.data?.items?.length) {
      employment.value = empListRes.data.items[0]
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function goToDetail() {
  emit('close')
  router.push(`/employees/${props.employeeId}`)
}

onMounted(loadData)
</script>

<template>
  <BaseDrawer :show="show" title="员工预览" @close="emit('close')">
    <div v-if="loading" class="drawer-loading text-tertiary">加载中...</div>
    <div v-else-if="employee" class="drawer-content">
      <div class="drawer-avatar">
        <EmployeeAvatar :name="employee.name" size="lg" />
      </div>

      <h3 class="drawer-name">{{ employee.name }}</h3>
      <div class="drawer-badges">
        <LifecycleBadge :status="employment?.employment_status || employee.employee_status" />
        <RiskBadge level="NONE" />
      </div>

      <div class="drawer-info">
        <div class="drawer-info-item">
          <span class="info-label">部门</span>
          <span class="info-value">{{ employment?.department || '—' }}</span>
        </div>
        <div class="drawer-info-item">
          <span class="info-label">岗位</span>
          <span class="info-value">{{ employment?.position || '—' }}</span>
        </div>
        <div class="drawer-info-item">
          <span class="info-label">入职日期</span>
          <span class="info-value">{{ formatDate(employment?.hire_date) }}</span>
        </div>
        <div class="drawer-info-item">
          <span class="info-label">在职时长</span>
          <span class="info-value">{{ formatTenure(employment?.hire_date) }}</span>
        </div>
      </div>

      <div class="drawer-section">
        <ProbationProgress
          :hire-date="employment?.hire_date"
          :probation-end-date="employment?.probation_end_date"
          size="sm"
        />
      </div>

      <button class="drawer-btn" @click="goToDetail">打开完整档案</button>
    </div>
  </BaseDrawer>
</template>

<style scoped>
.drawer-loading {
  text-align: center;
  padding: 48px;
}
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.drawer-avatar {
  display: flex;
  justify-content: center;
}
.drawer-name {
  text-align: center;
  font-size: var(--font-size-lg);
  font-weight: 600;
}
.drawer-badges {
  display: flex;
  justify-content: center;
  gap: 8px;
}
.drawer-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
}
.drawer-info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.info-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
.info-value {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  font-weight: 500;
}
.drawer-section {
  margin-top: 4px;
  padding: 12px 16px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
}
.drawer-btn {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  text-align: center;
  margin-top: 8px;
}
.drawer-btn:hover {
  background: var(--color-primary);
  color: #fff;
}
</style>
