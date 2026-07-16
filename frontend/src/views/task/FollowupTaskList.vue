<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import type { FollowupTaskItem } from '@/types'
import { getStatusLabel, followupStatusMap, confirmationModeMap } from '@/constants/status'
import { formatDate } from '@/utils/date'
import PageHeader from '@/components/layout/PageHeader.vue'

const router = useRouter()
const tasks = ref<FollowupTaskItem[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await get<{ items: FollowupTaskItem[]; total: number }>('/followup-tasks', { page: 1, page_size: 100 })
    if (res.success) tasks.value = res.data?.items || []
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <PageHeader title="跟进任务" subtitle="查看和管理员工跟进任务" />
    <div class="card table-card">
      <table v-if="tasks.length > 0">
        <thead>
          <tr>
            <th>任务名称</th>
            <th>计划日期</th>
            <th>状态</th>
            <th>确认模式</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td><span class="task-name">{{ task.task_name }}</span></td>
            <td>{{ formatDate(task.planned_date) }}</td>
            <td><span class="tag-status">{{ getStatusLabel(followupStatusMap, task.followup_status) }}</span></td>
            <td>{{ getStatusLabel(confirmationModeMap, task.confirmation_mode) }}</td>
            <td>
              <button class="table-btn" @click="router.push(`/followup-tasks/${task.id}`)">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline">暂无跟进任务</div>
      <div v-else class="empty-state-inline">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.table-card { overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.task-name { font-weight: 500; }
.tag-status { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: var(--font-size-xs); background: var(--color-bg); color: var(--color-text-secondary); }
.table-btn { padding: 3px 10px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); cursor: pointer; font-size: var(--font-size-xs); }
.empty-state-inline { text-align: center; padding: 48px; color: var(--color-text-tertiary); }
</style>
