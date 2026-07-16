<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch } from '@/api'
import type { EmploymentChangeItem, EmploymentItem } from '@/types'
import { useToast } from '@/composables/useToast'
import { formatDate } from '@/utils/date'
import { changeTypeMap, getStatusLabel } from '@/constants/status'
import ChangeDiffPanel from '@/components/business/ChangeDiffPanel.vue'
import PageHeader from '@/components/layout/PageHeader.vue'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()

const changeId = Number(route.params.id)
const employmentId = Number(route.params.employmentId || route.query.employment_id)

const isCreate = !changeId || route.path.endsWith('/create')
const change = ref<EmploymentChangeItem>({
  id: 0, employment_id: employmentId,
  change_type: 'DEPARTMENT', effective_date: '', created_at: '', version: 1,
})
const currentEmployment = ref<EmploymentItem | null>(null)
const saving = ref(false)
const afterDepartment = ref('')
const afterPosition = ref('')
const afterManager = ref('')

const pageTitle = computed(() => isCreate ? '新增异动' : '编辑异动')

const diffItems = computed(() => {
  const items: { label: string; before?: string; after?: string; changed: boolean }[] = []
  if (change.value.change_type === 'DEPARTMENT' || change.value.change_type === 'POSITION' || change.value.change_type === 'MANAGER') {
    items.push({
      label: '部门',
      before: currentEmployment.value?.department || '',
      after: afterDepartment.value || '',
      changed: !!(afterDepartment.value && afterDepartment.value !== currentEmployment.value?.department),
    })
    items.push({
      label: '岗位',
      before: currentEmployment.value?.position || '',
      after: afterPosition.value || '',
      changed: !!(afterPosition.value && afterPosition.value !== currentEmployment.value?.position),
    })
    items.push({
      label: '生效日期',
      before: currentEmployment.value?.hire_date ? formatDate(currentEmployment.value.hire_date) : '',
      after: change.value.effective_date || '',
      changed: !!change.value.effective_date,
    })
  }
  return items
})

const canSubmit = computed(() => {
  return diffItems.value.some((d) => d.changed)
})

async function loadData() {
  try {
    const empRes = await get<EmploymentItem>(`/employments/${employmentId}`)
    if (empRes.success && empRes.data) {
      currentEmployment.value = empRes.data
      afterDepartment.value = empRes.data.department || ''
      afterPosition.value = empRes.data.position || ''
    }

    if (!isCreate) {
      const res = await get<EmploymentChangeItem>(`/employment-changes/${changeId}`)
      if (res.success && res.data) {
        change.value = res.data
        if (typeof change.value.after_data === 'string') {
          try { change.value.after_data = JSON.parse(change.value.after_data) } catch {}
        }
        const after = change.value.after_data as any || {}
        afterDepartment.value = after.department || ''
        afterPosition.value = after.position || ''
      }
    }
  } catch (e: any) {
    console.error(e)
  }
}

async function handleSave() {
  if (!canSubmit.value) {
    showToast({ message: '至少修改一项任职信息', type: 'warning' })
    return
  }
  saving.value = true
  try {
    const afterData: Record<string, string> = {}
    if (afterDepartment.value && afterDepartment.value !== currentEmployment.value?.department) {
      afterData.department = afterDepartment.value
    }
    if (afterPosition.value && afterPosition.value !== currentEmployment.value?.position) {
      afterData.position = afterPosition.value
    }

    const body = {
      change_type: change.value.change_type,
      effective_date: change.value.effective_date,
      after_data: Object.keys(afterData).length > 0 ? afterData : null,
      reason: (change.value as any).reason || null,
    }

    if (isCreate) {
      const res = await post(`/employments/${employmentId}/changes`, body)
      if (res.success) {
        showToast({ message: '异动创建成功', type: 'success' })
        router.push(`/employments/${employmentId}/changes`)
      }
    } else {
      const res = await patch(`/employment-changes/${changeId}`, {
        effective_date: change.value.effective_date,
        after_data: afterData,
        reason: (change.value as any).reason || null,
      })
      if (res.success) {
        showToast({ message: '保存成功', type: 'success' })
        router.push(`/employments/${employmentId}/changes`)
      }
    }
  } catch (e: any) {
    showToast({ message: e.message || '保存失败', type: 'error' })
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <PageHeader :title="pageTitle" subtitle="管理员工任职异动信息" show-back @back="router.push(`/employments/${employmentId}/changes`)" />

    <!-- Current info -->
    <div class="card section-card" v-if="currentEmployment">
      <div class="section-title">当前任职信息</div>
      <div class="info-grid">
        <div class="info-item"><label>部门</label><span>{{ currentEmployment.department || '—' }}</span></div>
        <div class="info-item"><label>岗位</label><span>{{ currentEmployment.position || '—' }}</span></div>
        <div class="info-item"><label>入职日期</label><span>{{ formatDate(currentEmployment.hire_date) }}</span></div>
      </div>
    </div>

    <!-- Change form -->
    <div class="card section-card">
      <div class="section-title">异动后信息</div>
      <div class="form-grid">
        <div class="form-item">
          <label>异动类型</label>
          <select v-model="change.change_type" class="input" :disabled="!isCreate">
            <option v-for="(label, key) in changeTypeMap" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div class="form-item">
          <label>生效日期</label>
          <input v-model="change.effective_date" type="date" class="input" />
        </div>
        <div class="form-item">
          <label>新部门</label>
          <input v-model="afterDepartment" class="input" placeholder="输入新部门" />
        </div>
        <div class="form-item">
          <label>新岗位</label>
          <input v-model="afterPosition" class="input" placeholder="输入新岗位" />
        </div>
        <div class="form-item full-width">
          <label>变更原因</label>
          <textarea v-model="(change as any).reason" class="input textarea" rows="2" placeholder="输入变更原因" maxlength="500"></textarea>
        </div>
      </div>
    </div>

    <!-- Diff preview -->
    <div class="card section-card">
      <div class="section-title">变化预览</div>
      <ChangeDiffPanel :items="diffItems" />
    </div>

    <div class="form-actions">
      <button class="btn-cancel" @click="router.back()">取消</button>
      <button class="btn-primary" :disabled="saving || !canSubmit" @click="handleSave">
        {{ saving ? '保存中...' : '保存' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.section-card { padding: 20px; margin-bottom: 16px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item label { display: block; font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin-bottom: 4px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-item.full-width { grid-column: 1 / -1; }
.form-item label { display: block; font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin-bottom: 4px; }
.input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-sm); outline: none; }
.input:focus { border-color: var(--color-primary); }
.textarea { resize: vertical; font-family: inherit; }
select.input { background: var(--color-surface); }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.btn-primary { padding: 8px 20px; border: none; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; font-size: var(--font-size-sm); font-weight: 500; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-cancel { padding: 8px 20px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); font-size: var(--font-size-sm); cursor: pointer; }
</style>
