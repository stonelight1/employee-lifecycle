<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { FollowupTaskItem, CommunicationItem } from '@/types'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.id)
const task = ref<FollowupTaskItem | null>(null)

onMounted(async () => {
  try {
    const res = await get<FollowupTaskItem>(`/followup-tasks/${taskId}`)
    if (res.success) task.value = res.data!
  } catch (e: any) {
    console.error(e)
  }
})

async function handleStart() {
  try {
    await post(`/followup-tasks/${taskId}/start`)
    location.reload()
  } catch (e: any) {
    alert(e.message)
  }
}

async function handleComplete() {
  try {
    await post(`/followup-tasks/${taskId}/submit`)
    location.reload()
  } catch (e: any) {
    alert(e.message)
  }
}

async function handleCancel() {
  const reason = prompt('取消原因：')
  if (!reason) return
  try {
    await post(`/followup-tasks/${taskId}/cancel`, { reason })
    location.reload()
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div v-if="task" class="detail">
    <div class="detail-header">
      <button class="btn-back" @click="router.back()">← 返回</button>
      <h2>{{ task.task_name }}</h2>
      <span class="tag">{{ task.followup_status }}</span>
      <div class="header-actions">
        <button v-if="task.followup_status === 'PENDING'" class="btn btn-primary" @click="handleStart">开始处理</button>
        <button v-if="task.followup_status === 'IN_PROGRESS'" class="btn btn-primary" @click="handleComplete">提交</button>
        <button v-if="['PENDING', 'IN_PROGRESS'].includes(task.followup_status)" class="btn btn-danger" @click="handleCancel">取消</button>
      </div>
    </div>

    <div class="card">
      <div class="info-grid">
        <div class="info-item"><label>计划日期</label><span>{{ task.planned_date }}</span></div>
        <div class="info-item"><label>确认模式</label><span>{{ task.confirmation_mode }}</span></div>
        <div class="info-item"><label>节点快照</label><span>{{ task.node_code_snapshot || '-' }}</span></div>
        <div class="info-item"><label>偏移天数</label><span>{{ task.offset_days_snapshot ?? '-' }}</span></div>
      </div>
    </div>
  </div>
  <div v-else class="loading">加载中...</div>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  background: #fff;
  padding: 16px 24px;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.header-actions { margin-left: auto; display: flex; gap: 8px; }
.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item label { display: block; font-size: 12px; color: #909399; }
.btn-back { background: none; border: none; cursor: pointer; color: #409eff; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #f4f4f5; color: #909399; font-size: 12px; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; cursor: pointer; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-danger { color: #f56c6c; border-color: #f56c6c; }
.loading { text-align: center; padding: 48px; color: #909399; }
</style>
