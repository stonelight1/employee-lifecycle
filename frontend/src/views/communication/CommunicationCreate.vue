<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()

const employmentId = Number(route.query.employment_id)
const employeeId = Number(route.query.employee_id)
const communicationType = ref('PROBATION_FOLLOWUP')
const communicationText = ref('')
const manualSummary = ref('')
const hrConclusion = ref('')
const submitting = ref(false)
const employeeName = ref('')

onMounted(async () => {
  if (employeeId) {
    try {
      const res = await get<any>(`/employees/${employeeId}`)
      if (res.success) employeeName.value = res.data?.name || ''
    } catch {}
  }
})

async function handleSubmit() {
  if (!communicationText.value.trim()) {
    showToast({ type: 'error', message: '沟通文本不能为空' })
    return
  }
  submitting.value = true
  try {
    const res = await post('/communications', {
      employment_id: employmentId,
      communication_type: communicationType.value,
      communication_text: communicationText.value.trim(),
      manual_summary: manualSummary.value.trim() || null,
      hr_conclusion: hrConclusion.value.trim() || null,
    })
    if (res.success) {
      showToast({ type: 'success', message: '沟通记录已创建' })
      if (employeeId) {
        router.push(`/employees/${employeeId}`)
      } else {
        router.push('/employees')
      }
    }
  } catch (e: any) {
    showToast({ type: 'error', message: e.message || '创建失败' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">{{ employeeName ? `沟通记录 - ${employeeName}` : '新增沟通记录' }}</h1>
      <p class="page-subtitle">记录与员工的沟通内容</p>
    </div>

    <div class="card form-card">
      <div class="form-group">
        <label class="form-label">沟通类型</label>
        <select v-model="communicationType" class="form-select">
          <option value="PROBATION_FOLLOWUP">试用期跟进</option>
          <option value="REGULARIZATION_INTERVIEW">转正面谈</option>
          <option value="SEPARATION_TALK">离职面谈</option>
          <option value="ONBOARDING">入职沟通</option>
          <option value="GENERAL">一般沟通</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">沟通文本 <span class="text-danger">*</span></label>
        <textarea
          v-model="communicationText"
          class="form-textarea"
          rows="8"
          placeholder="请粘贴或输入沟通内容"
        />
      </div>

      <div class="form-group">
        <label class="form-label">HR 总结</label>
        <textarea
          v-model="manualSummary"
          class="form-textarea"
          rows="3"
          placeholder="HR 手工总结（可选）"
        />
      </div>

      <div class="form-group">
        <label class="form-label">HR 结论</label>
        <textarea
          v-model="hrConclusion"
          class="form-textarea"
          rows="2"
          placeholder="HR 结论（可选）"
        />
      </div>

      <div class="form-actions">
        <button class="action-btn secondary" @click="router.back()">取消</button>
        <button class="action-btn primary" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中...' : '保存沟通记录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-intro { margin-bottom: 20px; }
.form-card { max-width: 720px; padding: 24px; }
.form-group { margin-bottom: 20px; }
.form-label { display: block; font-size: var(--font-size-sm); font-weight: 500; margin-bottom: 6px; color: var(--color-text-secondary); }
.form-select, .form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
}
.form-select:focus, .form-textarea:focus {
  border-color: var(--color-primary);
}
.form-textarea { resize: vertical; min-height: 80px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid var(--color-border); }
.action-btn {
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
}
.action-btn.primary { background: var(--color-primary); color: #fff; }
.action-btn.primary:hover { background: var(--color-primary-hover); }
.action-btn.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.action-btn.secondary { background: var(--color-surface); color: var(--color-text-primary); border: 1px solid var(--color-border); }
</style>
