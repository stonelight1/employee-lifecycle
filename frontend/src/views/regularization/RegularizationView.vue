<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { RegularizationItem, ProbationReviewItem } from '@/types'

const route = useRoute()
const router = useRouter()
const employmentId = Number(route.params.employmentId)

const preview = ref<any>(null)
const records = ref<RegularizationItem[]>([])
const loading = ref(false)
const confirming = ref(false)

const decision = ref('APPROVED')
const decisionReason = ref('')
const effectiveDate = ref('')
const newProbationEndDate = ref('')

async function loadData() {
  loading.value = true
  try {
    const [prevRes, recRes] = await Promise.all([
      get<any>(`/employments/${employmentId}/regularization-preview`),
      get<{ items: RegularizationItem[]; total: number }>(`/employments/${employmentId}/regularization-records`),
    ])
    if (prevRes.success) preview.value = prevRes.data
    if (recRes.success && recRes.data) records.value = recRes.data.items

    // 默认转正日期
    if (prevRes.data?.probation_end_date) {
      effectiveDate.value = prevRes.data.probation_end_date
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleRegularize() {
  if (!confirm('确认执行转正操作？')) return
  confirming.value = true
  try {
    const body: Record<string, any> = { decision: decision.value, decision_reason: decisionReason.value || null }
    if (effectiveDate.value) body.effective_date = effectiveDate.value
    if (decision.value === 'EXTENDED' && newProbationEndDate.value) body.new_probation_end_date = newProbationEndDate.value

    const res = await post(`/employments/${employmentId}/regularize`, body)
    if (res.success) {
      alert('转正操作成功')
      await loadData()
    }
  } catch (e: any) {
    alert(e.message || '转正失败')
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
      <h2>转正管理</h2>
    </div>

    <!-- 转正预览 -->
    <div class="card" v-if="preview">
      <div class="section-title">转正预览</div>
      <div class="info-grid">
        <div class="info-item"><label>任职状态</label><span>{{ preview.employment_status || '-' }}</span></div>
        <div class="info-item"><label>入职日期</label><span>{{ preview.hire_date }}</span></div>
        <div class="info-item"><label>试用期开始</label><span>{{ preview.probation_start_date || '-' }}</span></div>
        <div class="info-item"><label>试用期结束</label><span>{{ preview.probation_end_date || '-' }}</span></div>
        <div class="info-item"><label>试用期状态</label><span>{{ preview.probation_status }}</span></div>
        <div class="info-item">
          <label>最终评估</label>
          <span v-if="preview.has_completed_final_review" class="tag tag-green">已完成</span>
          <span v-else class="tag tag-red">未完成</span>
        </div>
      </div>

      <div v-if="preview.warnings?.length" class="warnings">
        <div v-for="(w, i) in preview.warnings" :key="i" class="warning-item">⚠ {{ w }}</div>
      </div>

      <div v-if="!preview.can_regularize" class="notice">当前不满足转正条件，请先完成最终评估。</div>
    </div>

    <!-- 转正操作 -->
    <div class="card" v-if="preview?.can_regularize">
      <div class="section-title">执行转正</div>
      <div class="form-grid">
        <div class="form-item">
          <label>转正决策</label>
          <select v-model="decision" class="input">
            <option value="APPROVED">批准转正</option>
            <option value="EXTENDED">延长试用期</option>
            <option value="NOT_APPROVED">未通过</option>
          </select>
        </div>
        <div class="form-item">
          <label>生效日期</label>
          <input v-model="effectiveDate" type="date" class="input" />
        </div>
        <div class="form-item" v-if="decision === 'EXTENDED'">
          <label>新的试用期结束日期</label>
          <input v-model="newProbationEndDate" type="date" class="input" />
        </div>
        <div class="form-item full-width">
          <label>决策原因</label>
          <textarea v-model="decisionReason" class="input textarea" rows="3" placeholder="输入决策原因"></textarea>
        </div>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" :disabled="confirming" @click="handleRegularize">
          {{ confirming ? '提交中...' : `确认${decision === 'APPROVED' ? '转正' : decision === 'EXTENDED' ? '延期' : '不通过'}` }}
        </button>
      </div>
    </div>

    <!-- 转正历史 -->
    <div class="card">
      <div class="section-title">转正历史记录</div>
      <table v-if="records.length > 0">
        <thead>
          <tr>
            <th>决策</th>
            <th>生效日期</th>
            <th>原因</th>
            <th>确认人</th>
            <th>确认时间</th>
            <th>有效</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td><span class="tag" :class="{'tag-green': r.decision === 'APPROVED', 'tag-orange': r.decision === 'EXTENDED', 'tag-red': r.decision === 'NOT_APPROVED'}">{{ r.decision }}</span></td>
            <td>{{ r.effective_date || '-' }}</td>
            <td>{{ r.decision_reason || '-' }}</td>
            <td>{{ r.confirmed_by || '-' }}</td>
            <td>{{ r.confirmed_at?.slice(0, 10) || '-' }}</td>
            <td>{{ r.is_effective ? '是' : '否' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">暂无转正记录</div>
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
select.input { background: #fff; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.tag-green { background: #e1f3d8; color: #67c23a; }
.tag-red { background: #fef0f0; color: #f56c6c; }
.tag-orange { background: #faecd8; color: #e6a23c; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.empty { text-align: center; padding: 48px; color: #909399; }
.warnings { margin-top: 12px; }
.warning-item { background: #fdf6ec; color: #e6a23c; padding: 8px 12px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.notice { background: #f0f9eb; color: #67c23a; padding: 12px; border-radius: 4px; margin-top: 12px; font-size: 13px; }
</style>
