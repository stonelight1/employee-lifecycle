<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get, del } from '@/api'
import type { FollowupTaskItem } from '@/types'

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
  <div>
    <div class="page-header">
      <h2>跟进任务</h2>
    </div>
    <div class="table-card">
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
            <td>{{ task.task_name }}</td>
            <td>{{ task.planned_date }}</td>
            <td><span class="tag">{{ task.followup_status }}</span></td>
            <td>{{ task.confirmation_mode }}</td>
            <td>
              <button class="btn btn-sm" @click="router.push(`/followup-tasks/${task.id}`)">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">{{ loading ? '加载中...' : '暂无跟进任务' }}</div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.table-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
