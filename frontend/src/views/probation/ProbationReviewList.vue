<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get } from '@/api'
import type { ProbationReviewItem } from '@/types'
import { getStatusLabel, reviewStatusMap, reviewStageMap } from '@/constants/status'

const route = useRoute()
const router = useRouter()
const employmentId = Number(route.params.employmentId)

const reviews = ref<ProbationReviewItem[]>([])
const loading = ref(false)
const total = ref(0)

async function loadReviews() {
  loading.value = true
  try {
    const res = await get<{ items: ProbationReviewItem[]; total: number }>(`/employments/${employmentId}/probation-reviews`)
    if (res.success && res.data) {
      reviews.value = res.data.items
      total.value = res.data.total
    }
  } catch (e: any) {
    console.error('加载试用期评估失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadReviews)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <button class="btn-back" @click="router.back()">← 返回</button>
      <h2>试用期评估</h2>
      <button class="btn btn-primary" @click="router.push(`/employments/${employmentId}/probation-reviews/create`)">新增评估</button>
    </div>

    <div class="card">
      <table v-if="reviews.length > 0">
        <thead>
          <tr>
            <th>序号</th>
            <th>评估阶段</th>
            <th>状态</th>
            <th>建议</th>
            <th>评估人</th>
            <th>评估时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in reviews" :key="r.id">
            <td>#{{ r.review_seq }}</td>
            <td>
              <span class="tag" :class="r.review_stage === 'FINAL' ? 'tag-orange' : 'tag-blue'">
                {{ getStatusLabel(reviewStageMap, r.review_stage) }}
              </span>
            </td>
            <td><span class="tag">{{ getStatusLabel(reviewStatusMap, r.review_status) }}</span></td>
            <td>{{ r.recommendation || '-' }}</td>
            <td>{{ r.reviewed_by || '-' }}</td>
            <td>{{ r.reviewed_at?.slice(0, 10) || '-' }}</td>
            <td>
              <button class="btn btn-sm" @click="router.push(`/probation-reviews/${r.id}?employment_id=${employmentId}`)">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">暂无试用期评估记录</div>
      <div v-else class="empty">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; background: #fff; padding: 16px 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.btn-back { background: none; border: none; cursor: pointer; color: #409eff; font-size: 14px; }
h2 { flex: 1; font-size: 18px; margin: 0; }
.card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.tag-blue { background: #d9ecff; color: #409eff; }
.tag-orange { background: #faecd8; color: #e6a23c; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-sm { padding: 4px 10px; margin-right: 4px; font-size: 12px; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
