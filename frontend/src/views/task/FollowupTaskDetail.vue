<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { FollowupTaskItem } from '@/types'
import { getStatusLabel, followupStatusMap, confirmationModeMap } from '@/constants/status'
import { formatDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseModal from '@/components/base/BaseModal.vue'
import PageHeader from '@/components/layout/PageHeader.vue'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

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
    showToast({ message: '任务已开始处理', type: 'success' })
    const res = await get<FollowupTaskItem>(`/followup-tasks/${taskId}`)
    if (res.success) task.value = res.data!
  } catch (e: any) {
    showToast({ message: e.message || '操作失败', type: 'error' })
  }
}

async function handleComplete() {
  try {
    await post(`/followup-tasks/${taskId}/submit`)
    showToast({ message: '任务已完成', type: 'success' })
    const res = await get<FollowupTaskItem>(`/followup-tasks/${taskId}`)
    if (res.success) task.value = res.data!
  } catch (e: any) {
    showToast({ message: e.message || '操作失败', type: 'error' })
  }
}

async function cancelTask() {
  confirm({
    title: '取消任务',
    message: '请输入取消原因',
    confirmText: '确认取消',
    danger: true,
    onConfirm: async () => {
      try {
        await post(`/followup-tasks/${taskId}/cancel`, { reason: '' })
        showToast({ message: '任务已取消', type: 'success' })
        const res = await get<FollowupTaskItem>(`/followup-tasks/${taskId}`)
        if (res.success) task.value = res.data!
      } catch (e: any) {
        showToast({ message: e.message || '操作失败', type: 'error' })
      }
    },
  })
}
</script>

<template>
  <div class="page">
    <PageHeader :title="task?.task_name || '任务详情'" subtitle="查看和管理跟进任务详情" show-back @back="router.back()" />

    <div v-if="task" class="card section-card">
      <div class="flex justify-between items-center" style="margin-bottom: 16px;">
        <div>
          <h2 class="text-md" style="font-weight: 600;">{{ task.task_name }}</h2>
          <span class="text-xs text-tertiary">状态: {{ getStatusLabel(followupStatusMap, task.followup_status) }}</span>
        </div>
        <div class="flex gap-2">
          <button v-if="task.followup_status === 'PENDING'" class="btn-primary-sm" @click="handleStart">开始处理</button>
          <button v-if="task.followup_status === 'IN_PROGRESS'" class="btn-primary-sm" @click="handleComplete">提交</button>
          <button v-if="['PENDING', 'IN_PROGRESS'].includes(task.followup_status)" class="btn-danger-sm" @click="cancelTask">取消</button>
        </div>
      </div>

      <div class="info-grid">
        <div class="info-item"><label>计划日期</label><span>{{ formatDate(task.planned_date) }}</span></div>
        <div class="info-item"><label>确认模式</label><span>{{ getStatusLabel(confirmationModeMap, task.confirmation_mode) }}</span></div>
        <div class="info-item"><label>节点快照</label><span>{{ task.node_code_snapshot || '-' }}</span></div>
        <div class="info-item"><label>偏移天数</label><span>{{ task.offset_days_snapshot ?? '-' }}</span></div>
      </div>
    </div>
    <div v-else class="loading-state text-tertiary">加载中...</div>

    <BaseModal
      :show="showConfirm"
      :title="confirmOpts.title"
      :message="confirmOpts.message"
      :confirm-text="confirmOpts.confirmText"
      :danger="confirmOpts.danger"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>

<style scoped>
.section-card { padding: 20px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item label { display: block; font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin-bottom: 4px; }
.btn-primary-sm { padding: 6px 14px; border: none; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; font-size: var(--font-size-sm); cursor: pointer; }
.btn-danger-sm { padding: 6px 14px; border: 1px solid var(--color-danger); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-danger); font-size: var(--font-size-sm); cursor: pointer; }
.text-xs { font-size: var(--font-size-xs); }
.text-tertiary { color: var(--color-text-tertiary); }
.flex { display: flex; }
.justify-between { justify-content: space-between; }
.items-center { align-items: center; }
.gap-2 { gap: 8px; }
</style>
