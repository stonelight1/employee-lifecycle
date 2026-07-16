<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get } from '@/api'
import type { EmploymentItem, FollowupTaskItem, CommunicationItem } from '@/types'
import { getStatusLabel, employmentStatusMap, probationStatusMap, followupStatusMap, communicationStatusMap, communicationTypeMap } from '@/constants/status'
import PageHeader from '@/components/layout/PageHeader.vue'

const route = useRoute()
const router = useRouter()
const employmentId = Number(route.params.employmentId)
const employeeId = Number(route.params.id)

const employment = ref<EmploymentItem | null>(null)
const tasks = ref<FollowupTaskItem[]>([])
const communications = ref<CommunicationItem[]>([])

onMounted(async () => {
  try {
    const empRes = await get<EmploymentItem>(`/employments/${employmentId}`)
    if (empRes.success) employment.value = empRes.data!

    const taskRes = await get<{ items: FollowupTaskItem[]; total: number }>('/followup-tasks', { employment_id: employmentId })
    if (taskRes.success) tasks.value = taskRes.data?.items || []

    const commRes = await get<{ items: CommunicationItem[]; total: number }>('/communications', { employment_id: employmentId })
    if (commRes.success) communications.value = commRes.data?.items || []
  } catch (e: any) {
    console.error(e)
  }
})
</script>

<template>
  <div class="page">
    <PageHeader title="任职详情" subtitle="查看员工任职详细信息和相关记录" show-back @back="router.push(`/employees/${employeeId}`)" />

    <div class="card" v-if="employment">
      <div class="section-title">基本信息</div>
      <div class="info-grid">
        <div class="info-item"><label>入职日期</label><span>{{ employment.hire_date }}</span></div>
        <div class="info-item"><label>任职状态</label><span>{{ getStatusLabel(employmentStatusMap, employment.employment_status) }}</span></div>
        <div class="info-item"><label>试用期状态</label><span>{{ getStatusLabel(probationStatusMap, employment.probation_status) }}</span></div>
        <div class="info-item"><label>试用期结束</label><span>{{ employment.probation_end_date || '-' }}</span></div>
        <div class="info-item"><label>部门</label><span>{{ employment.department || '-' }}</span></div>
        <div class="info-item"><label>岗位</label><span>{{ employment.position || '-' }}</span></div>
        <div class="info-item"><label>转正日期</label><span>{{ employment.regularization_date || '-' }}</span></div>
        <div class="info-item"><label>离职日期</label><span>{{ employment.separation_date || '-' }}</span></div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">
        跟进任务
        <span class="action-links">
          <router-link :to="`/employments/${employmentId}/probation-reviews`">试用期评估</router-link>
          <router-link :to="`/employments/${employmentId}/regularization`">转正</router-link>
          <router-link :to="`/employments/${employmentId}/separation`">离职</router-link>
          <router-link :to="`/employments/${employmentId}/changes`">异动</router-link>
        </span>
      </div>
      <div v-if="tasks.length === 0" class="empty">暂无跟进任务</div>
      <div v-for="task in tasks" :key="task.id" class="task-row">
        <span class="task-name">{{ task.task_name }}</span>
        <span class="tag" :class="`tag-${task.followup_status.toLowerCase()}`">{{ getStatusLabel(followupStatusMap, task.followup_status) }}</span>
        <span class="task-date">{{ task.planned_date }}</span>
        <button class="btn btn-sm" @click="router.push(`/followup-tasks/${task.id}`)">查看</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">沟通记录</div>
      <button class="btn btn-primary" @click="router.push(`/communications/new?employment_id=${employmentId}`)">新建沟通</button>
      <div v-if="communications.length === 0" class="empty">暂无沟通记录</div>
      <div v-for="comm in communications" :key="comm.id" class="comm-row">
        <span>{{ getStatusLabel(communicationTypeMap, comm.communication_type) }}</span>
        <span class="tag">{{ getStatusLabel(communicationStatusMap, comm.communication_status) }}</span>
        <span>{{ comm.created_at?.slice(0, 10) }}</span>
        <button class="btn btn-sm" @click="router.push(`/communications/${comm.id}`)">查看</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.action-links {
  font-size: 13px;
  font-weight: 400;
  display: flex;
  gap: 12px;
}
.action-links a {
  color: #409eff;
  text-decoration: none;
  cursor: pointer;
}
.action-links a:hover {
  text-decoration: underline;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.info-item label {
  display: block;
  font-size: 12px;
  color: #909399;
}
.task-row, .comm-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}
.task-name {
  flex: 1;
}
.task-date {
  color: #909399;
  font-size: 13px;
}
.empty { text-align: center; padding: 32px; color: #909399; }
</style>
