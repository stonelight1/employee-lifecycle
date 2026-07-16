<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch } from '@/api'
import { useToast } from '@/composables/useToast'
import type { ProbationReviewItem, FollowupTaskItem, CommunicationItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const reviewId = Number(route.params.id)
const employmentId = Number(route.query.employment_id)

const isCreate = reviewId === 0 || route.path.endsWith('/create')
const review = ref<ProbationReviewItem>({
  id: 0, employment_id: employmentId,
  review_stage: 'FOLLOWUP', review_status: 'DRAFT',
  review_seq: 1, version: 1,
})
const followupTasks = ref<FollowupTaskItem[]>([])
const communications = ref<CommunicationItem[]>([])
const saving = ref(false)
const isCompleting = ref(false)

const pageTitle = computed(() => isCreate ? '新增试用期评估' : '试用期评估详情')

async function loadReview() {
  if (isCreate) return
  try {
    const res = await get<ProbationReviewItem>(`/probation-reviews/${reviewId}`)
    if (res.success && res.data) review.value = res.data
  } catch (e: any) {
    console.error(e)
  }
}

async function loadOptions() {
  try {
    const [taskRes, commRes] = await Promise.all([
      get<{ items: FollowupTaskItem[]; total: number }>('/followup-tasks', { employment_id: employmentId, page_size: 100 }),
      get<{ items: CommunicationItem[]; total: number }>('/communications', { employment_id: employmentId, page_size: 100 }),
    ])
    if (taskRes.success && taskRes.data) followupTasks.value = taskRes.data.items
    if (commRes.success && commRes.data) communications.value = commRes.data.items
  } catch (e: any) {
    console.error(e)
  }
}

async function handleSave() {
  saving.value = true
  try {
    if (isCreate) {
      const res = await post(`/employments/${employmentId}/probation-reviews`, {
        employment_id: employmentId,
        review_stage: review.value.review_stage,
        followup_task_id: review.value.followup_task_id || null,
        communication_id: review.value.communication_id || null,
        hr_evaluation: review.value.hr_evaluation || null,
        employee_feedback: review.value.employee_feedback || null,
        recommendation: review.value.recommendation || null,
      })
      if (res.success) {
        showToast({ type: 'success', message: '创建成功' })
        router.push(`/employments/${employmentId}/probation-reviews`)
      }
    } else {
      const res = await patch<ProbationReviewItem>(`/probation-reviews/${reviewId}`, {
        hr_evaluation: review.value.hr_evaluation || null,
        employee_feedback: review.value.employee_feedback || null,
        recommendation: review.value.recommendation || null,
      })
      if (res.success && res.data) {
        showToast({ type: 'success', message: '保存成功' })
        Object.assign(review.value, res.data)
      }
    }
  } catch (e: any) {
    showToast({ type: 'error', message: e.message || '保存失败' })
  } finally {
    saving.value = false
  }
}

async function handleComplete() {
  isCompleting.value = true
  try {
    const res = await post<ProbationReviewItem>(`/probation-reviews/${reviewId}/complete`, {
      review_status: 'COMPLETED',
      hr_evaluation: review.value.hr_evaluation || null,
      employee_feedback: review.value.employee_feedback || null,
      recommendation: review.value.recommendation || null,
    })
    if (res.success && res.data) {
      showToast({ type: 'success', message: '评估已完成' })
      Object.assign(review.value, res.data)
    }
  } catch (e: any) {
    showToast({ type: 'error', message: e.message || '完成失败' })
  } finally {
    isCompleting.value = false
  }
}

onMounted(() => {
  loadReview()
  loadOptions()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <button class="btn-back" @click="router.push(`/employments/${employmentId}/probation-reviews`)">← 返回列表</button>
      <h2>{{ pageTitle }}</h2>
    </div>

    <div class="card">
      <div class="section-title">评估信息</div>
      <div class="form-grid">
        <div class="form-item">
          <label>评估阶段</label>
          <select v-model="review.review_stage" :disabled="!isCreate" class="input">
            <option value="FOLLOWUP">过程评估</option>
            <option value="FINAL">最终评估</option>
          </select>
        </div>
        <div class="form-item">
          <label>关联任务</label>
          <select v-model="review.followup_task_id" class="input">
            <option :value="undefined">- 不关联 -</option>
            <option v-for="t in followupTasks" :key="t.id" :value="t.id">{{ t.task_name }}</option>
          </select>
        </div>
        <div class="form-item">
          <label>关联沟通</label>
          <select v-model="review.communication_id" class="input">
            <option :value="undefined">- 不关联 -</option>
            <option v-for="c in communications" :key="c.id" :value="c.id">沟通 #{{ c.id }} {{ c.created_at?.slice(0, 10) }}</option>
          </select>
        </div>
        <div class="form-item" v-if="!isCreate">
          <label>状态</label>
          <span class="tag">{{ review.review_status || 'DRAFT' }}</span>
        </div>
        <div class="form-item full-width">
          <label>HR 评估内容</label>
          <textarea v-model="review.hr_evaluation" class="input textarea" rows="4" placeholder="输入评估内容"></textarea>
        </div>
        <div class="form-item full-width">
          <label>员工反馈</label>
          <textarea v-model="review.employee_feedback" class="input textarea" rows="3" placeholder="输入员工反馈"></textarea>
        </div>
        <div class="form-item full-width">
          <label>建议</label>
          <textarea v-model="review.recommendation" class="input textarea" rows="2" placeholder="输入建议（最多 500 字）" maxlength="500"></textarea>
        </div>
      </div>

      <div class="form-actions">
        <button class="btn" @click="router.back()">取消</button>
        <button v-if="isCreate || review.review_status !== 'COMPLETED'" class="btn btn-primary" :disabled="saving" @click="handleSave">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button v-if="!isCreate && review.review_status !== 'COMPLETED'" class="btn btn-success" :disabled="isCompleting" @click="handleComplete">
          {{ isCompleting ? '提交中...' : '完成评估' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; background: #fff; padding: 16px 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.btn-back { background: none; border: none; cursor: pointer; color: #409eff; font-size: 14px; }
h2 { flex: 1; font-size: 18px; margin: 0; }
.card { background: #fff; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #ebeef5; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-item.full-width { grid-column: 1 / -1; }
.form-item label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.textarea { resize: vertical; font-family: inherit; }
select.input { background: #fff; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-success { background: #67c23a; color: #fff; border-color: #67c23a; }
.btn-primary:disabled, .btn-success:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
