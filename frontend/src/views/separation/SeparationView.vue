<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { SeparationItem } from '@/types'

const route = useRoute()
const router = useRouter()
const employmentId = Number(route.params.employmentId)

const preview = ref<any>(null)
const records = ref<SeparationItem[]>([])
const loading = ref(false)
const starting = ref(false)
const confirming = ref(false)

const separationType = ref('')
const reason = ref('')
const plannedDate = ref('')
const actualDate = ref('')
const hrComment = ref('')

async function loadData() {
  loading.value = true
  try {
    const [prevRes, recRes] = await Promise.all([
      get<any>(`/employments/${employmentId}/separation-preview`),
      get<{ items: SeparationItem[]; total: number }>(`/employments/${employmentId}/separation-records`),
    ])
    if (prevRes.success) preview.value = prevRes.data
    if (recRes.success && recRes.data) records.value = recRes.data.items
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  starting.value = true
  try {
    const res = await post(`/employments/${employmentId}/start-separation`, {
      planned_separation_date: plannedDate.value || null,
      separation_type: separationType.value || null,
      reason: reason.value || null,
      hr_comment: hrComment.value || null,
    })
    if (res.success) {
      alert('离职流程已启动')
      await loadData()
    }
  } catch (e: any) {
    alert(e.message || '启动失败')
  } finally {
    starting.value = false
  }
}

async function handleConfirm() {
  if (!confirm('确认离职？此操作将取消所有未完成任务。')) return
  confirming.value = true
  try {
    const res = await post(`/employments/${employmentId}/confirm-separation`, {
      actual_separation_date: actualDate.value || null,
      hr_comment: hrComment.value || null,
      confirm: true,
    })
    if (res.success) {
      alert('离职已确认')
      await loadData()
    }
  } catch (e: any) {
    alert(e.message || '确认失败')
  } finally {
    confirming.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <button class="btn-back" @click="router.back()">← 返回</button>
      <h2>离职管理</h2>
    </div>

    <!-- 离职预览 -->
    <div class="card" v-if="preview">
      <div class="section-title">离职预览</div>
      <div class="info-grid">
        <div class="info-item"><label>当前任职状态</label><span class="tag">{{ preview.employment_status }}</span></div>
        <div class="info-item"><label>入职日期</label><span>{{ preview.hire_date }}</span></div>
        <div class="info-item"><label>待处理任务数</label><span>{{ preview.pending_tasks_count }}</span></div>
        <div class="info-item"><label>待处理待办数</label><span>{{ preview.pending_todos_count }}</span></div>
      </div>

      <div v-if="preview.warnings?.length" class="warnings">
        <div v-for="(w, i) in preview.warnings" :key="i" class="warning-item">⚠ {{ w }}</div>
      </div>

      <div v-if="!preview.can_start_separation" class="notice">当前任职状态不允许启动离职。</div>
    </div>

    <!-- 启动离职 -->
    <div class="card" v-if="preview?.can_start_separation && preview.employment_status !== 'SEPARATING' && preview.employment_status !== 'SEPARATED'">
      <div class="section-title">启动离职流程</div>
      <div class="form-grid">
        <div class="form-item">
          <label>离职类型</label>
          <input v-model="separationType" class="input" placeholder="如: 主动离职、协商解除" />
        </div>
        <div class="form-item">
          <label>计划离职日期</label>
          <input v-model="plannedDate" type="date" class="input" />
        </div>
        <div class="form-item full-width">
          <label>离职原因</label>
          <textarea v-model="reason" class="input textarea" rows="3" placeholder="输入离职原因"></textarea>
        </div>
        <div class="form-item full-width">
          <label>HR 备注</label>
          <textarea v-model="hrComment" class="input textarea" rows="2" placeholder="HR 备注"></textarea>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-warning" :disabled="starting" @click="handleStart">
          {{ starting ? '提交中...' : '启动离职流程' }}
        </button>
      </div>
    </div>

    <!-- 确认离职 -->
    <div class="card" v-if="preview?.employment_status === 'SEPARATING'">
      <div class="section-title">确认离职</div>
      <div class="form-grid">
        <div class="form-item">
          <label>实际离职日期</label>
          <input v-model="actualDate" type="date" class="input" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-danger" :disabled="confirming" @click="handleConfirm">
          {{ confirming ? '提交中...' : '确认离职' }}
        </button>
      </div>
    </div>

    <!-- 离职历史 -->
    <div class="card">
      <div class="section-title">离职记录</div>
      <table v-if="records.length > 0">
        <thead>
          <tr>
            <th>离职类型</th>
            <th>原因</th>
            <th>计划日期</th>
            <th>实际日期</th>
            <th>确认人</th>
            <th>确认时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ r.separation_type || '-' }}</td>
            <td>{{ r.reason || '-' }}</td>
            <td>{{ r.actual_separation_date || '-' }}</td>
            <td>{{ r.actual_separation_date || '-' }}</td>
            <td>{{ r.confirmed_by || '-' }}</td>
            <td>{{ r.confirmed_at?.slice(0, 10) || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">暂无离职记录</div>
      <div v-else class="empty">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; background: #fff; padding: 16px 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.btn-back { background: none; border: none; cursor: pointer; color: #409eff; font-size: 14px; }
h2 { flex: 1; font-size: 18px; margin: 0; }
.card { background: #fff; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #ebeef5; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item label { display: block; font-size: 12px; color: #909399; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-item.full-width { grid-column: 1 / -1; }
.form-item label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.textarea { resize: vertical; font-family: inherit; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-warning { background: #e6a23c; color: #fff; border-color: #e6a23c; }
.btn-danger { background: #f56c6c; color: #fff; border-color: #f56c6c; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.empty { text-align: center; padding: 48px; color: #909399; }
.warnings { margin-top: 12px; }
.warning-item { background: #fdf6ec; color: #e6a23c; padding: 8px 12px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.notice { background: #f0f9eb; color: #67c23a; padding: 12px; border-radius: 4px; margin-top: 12px; font-size: 13px; }
</style>
