<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { RegularizationItem } from '@/types'
import { formatDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { getStatusLabel, employmentStatusMap, regularizationDecisionMap } from '@/constants/status'
import BaseModal from '@/components/base/BaseModal.vue'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const employmentId = Number(route.params.employmentId)
const preview = ref<any>(null)
const records = ref<RegularizationItem[]>([])
const loading = ref(false)
const confirming = ref(false)
const step = ref(1)

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
    if (prevRes.success) {
      preview.value = prevRes.data
      if (prevRes.data?.probation_end_date) {
        effectiveDate.value = prevRes.data.probation_end_date
      }
    }
    if (recRes.success && recRes.data) records.value = recRes.data.items
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleRegularize() {
  confirm({
    title: '确认转正操作',
    message: `确认后：\n- 任职状态将从"试用期"变为"正式在职"\n- 未完成的试用期跟进任务将按业务规则处理\n- 操作将写入员工时间线和操作日志`,
    confirmText: '确认转为正式员工',
    onConfirm: async () => {
      confirming.value = true
      try {
        const body: Record<string, any> = { decision: decision.value, decision_reason: decisionReason.value || null }
        if (effectiveDate.value) body.effective_date = effectiveDate.value
        if (decision.value === 'EXTENDED' && newProbationEndDate.value) body.new_probation_end_date = newProbationEndDate.value

        const res = await post(`/employments/${employmentId}/regularize`, body)
        if (res.success) {
          showToast({ message: '转正操作成功', type: 'success' })
          await loadData()
        }
      } catch (e: any) {
        showToast({ message: e.message || '转正失败', type: 'error' })
      } finally {
        confirming.value = false
      }
    },
  })
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <button class="back-link" @click="router.back()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        返回
      </button>
      <h1 class="page-title">转正管理</h1>
    </div>

    <!-- Steps -->
    <div class="steps-bar">
      <div class="step" :class="{ active: step === 1, completed: step > 1 }">
        <div class="step-num">1</div>
        <span class="step-label">转正预览</span>
      </div>
      <div class="step-connector" :class="{ active: step > 1 }" />
      <div class="step" :class="{ active: step === 2, completed: step > 2 }">
        <div class="step-num">2</div>
        <span class="step-label">补充结论</span>
      </div>
      <div class="step-connector" :class="{ active: step > 2 }" />
      <div class="step" :class="{ active: step === 3, completed: step > 3 }">
        <div class="step-num">3</div>
        <span class="step-label">确认转正</span>
      </div>
      <div class="step-connector" :class="{ active: step > 3 }" />
      <div class="step" :class="{ active: step === 4, completed: step > 4 }">
        <div class="step-num">4</div>
        <span class="step-label">完成</span>
      </div>
    </div>

    <!-- Preview -->
    <div class="card section-card" v-if="preview">
      <div class="section-title">转正预览</div>
      <div class="info-grid">
        <div class="info-item"><label>任职状态</label><span>{{ getStatusLabel(employmentStatusMap, preview.employment_status) }}</span></div>
        <div class="info-item"><label>入职日期</label><span>{{ formatDate(preview.hire_date) }}</span></div>
        <div class="info-item"><label>试用期开始</label><span>{{ formatDate(preview.probation_start_date) }}</span></div>
        <div class="info-item"><label>试用期结束</label><span>{{ formatDate(preview.probation_end_date) }}</span></div>
        <div class="info-item"><label>试用期状态</label><span>{{ preview.probation_status || '-' }}</span></div>
        <div class="info-item">
          <label>最终评估</label>
          <span v-if="preview.has_completed_final_review" style="color: var(--color-success);">已完成</span>
          <span v-else style="color: var(--color-warning);">未完成</span>
        </div>
      </div>

      <div v-if="preview.warnings?.length" class="warnings">
        <div v-for="(w, i) in preview.warnings" :key="i" class="warning-item">⚠ {{ w }}</div>
      </div>
    </div>

    <!-- Form -->
    <div class="card section-card" v-if="preview?.can_regularize">
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

      <!-- Impact notice -->
      <div class="impact-notice">
        <p class="text-sm">确认后：任职状态将从"试用期"变为"正式在职"</p>
      </div>

      <div class="form-actions">
        <button class="btn-primary" :disabled="confirming" @click="handleRegularize">
          {{ confirming ? '提交中...' : `确认${decision === 'APPROVED' ? '转为正式员工' : decision === 'EXTENDED' ? '延长试用期' : '不通过'}` }}
        </button>
      </div>
    </div>

    <!-- History -->
    <div class="card section-card">
      <div class="section-title">转正历史记录</div>
      <table v-if="records.length > 0" class="data-table">
        <thead>
          <tr>
            <th>决策</th>
            <th>生效日期</th>
            <th>原因</th>
            <th>确认人</th>
            <th>确认时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ getStatusLabel(regularizationDecisionMap, r.decision) }}</td>
            <td>{{ formatDate(r.effective_date) }}</td>
            <td>{{ r.decision_reason || '-' }}</td>
            <td>{{ r.confirmed_by || '-' }}</td>
            <td>{{ formatDate(r.confirmed_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline text-tertiary">暂无转正记录</div>
    </div>

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
.page-intro {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 20px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  width: fit-content;
}
.back-link:hover { color: var(--color-primary); }

/* Steps */
.steps-bar {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-sm);
  font-weight: 600;
  background: var(--color-bg);
  color: var(--color-text-tertiary);
  border: 2px solid var(--color-border);
}
.step.active .step-num {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.step.completed .step-num {
  background: var(--color-success);
  color: #fff;
  border-color: var(--color-success);
}
.step-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  white-space: nowrap;
}
.step.active .step-label { color: var(--color-primary); font-weight: 500; }
.step.completed .step-label { color: var(--color-success); }

.step-connector {
  flex: 1;
  height: 2px;
  background: var(--color-border);
  margin: 0 12px;
}
.step-connector.active { background: var(--color-success); }

.section-card {
  padding: 20px;
  margin-bottom: 16px;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.info-item label { display: block; font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin-bottom: 4px; }
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-item.full-width { grid-column: 1 / -1; }
.form-item label { display: block; font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin-bottom: 4px; }
.input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-sm); outline: none; }
.input:focus { border-color: var(--color-primary); }
.textarea { resize: vertical; font-family: inherit; }
select.input { background: var(--color-surface); }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.btn-primary { padding: 8px 20px; border: none; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; font-size: var(--font-size-sm); font-weight: 500; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.impact-notice {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
  color: var(--color-primary);
}

.warnings { margin-top: 12px; }
.warning-item { background: var(--color-warning-soft); color: var(--color-warning); padding: 8px 12px; border-radius: var(--radius-sm); margin-bottom: 4px; font-size: var(--font-size-sm); }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.data-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.empty-state-inline { text-align: center; padding: 32px; font-size: var(--font-size-sm); }
</style>
