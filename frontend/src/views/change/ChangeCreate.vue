<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch } from '@/api'
import type { EmploymentChangeItem } from '@/types'

const route = useRoute()
const router = useRouter()
const changeId = Number(route.params.id)
const employmentId = Number(route.params.employmentId || route.query.employment_id)

const isCreate = !changeId || route.path.endsWith('/create')
const change = ref<EmploymentChangeItem>({
  id: 0, employment_id: employmentId,
  change_type: 'DEPARTMENT', effective_date: '', created_at: '', version: 1,
})
const saving = ref(false)

const pageTitle = computed(() => isCreate ? '新增异动' : '编辑异动')

async function loadChange() {
  if (isCreate) return
  try {
    const res = await get<EmploymentChangeItem>(`/employment-changes/${changeId}`)
    if (res.success && res.data) {
      change.value = res.data
      if (typeof change.value.after_data === 'string') {
        try { change.value.after_data = JSON.parse(change.value.after_data) } catch {}
      }
    }
  } catch (e: any) {
    console.error(e)
  }
}

async function handleSave() {
  saving.value = true
  try {
    const body = {
      change_type: change.value.change_type,
      effective_date: change.value.effective_date,
      after_data: change.value.after_data || null,
      reason: (change.value as any).reason || null,
    }

    if (isCreate) {
      const res = await post(`/employments/${employmentId}/changes`, body)
      if (res.success) {
        alert('创建成功')
        router.push(`/employments/${employmentId}/changes`)
      }
    } else {
      const res = await patch(`/employment-changes/${changeId}`, {
        effective_date: change.value.effective_date,
        after_data: change.value.after_data || null,
        reason: (change.value as any).reason || null,
      })
      if (res.success) {
        alert('保存成功')
        router.push(`/employments/${employmentId}/changes`)
      }
    }
  } catch (e: any) {
    alert(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const changeTypeLabels: Record<string, string> = {
  DEPARTMENT: '部门变更',
  POSITION: '岗位变更',
  MANAGER: '负责人变更',
}

onMounted(loadChange)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <button class="btn-back" @click="router.push(`/employments/${employmentId}/changes`)">← 返回列表</button>
      <h2>{{ pageTitle }}</h2>
    </div>

    <div class="card">
      <div class="form-grid">
        <div class="form-item">
          <label>异动类型</label>
          <select v-model="change.change_type" class="input" :disabled="!isCreate">
            <option v-for="(label, key) in changeTypeLabels" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div class="form-item">
          <label>生效日期</label>
          <input v-model="change.effective_date" type="date" class="input" />
        </div>
        <div class="form-item full-width">
          <label>变更后内容 (JSON)</label>
          <textarea v-model="(change as any).after_data_display" class="input textarea" rows="4"
            placeholder='如: {"department": "技术部", "position": "高级工程师"}'
            @input="(e: any) => { try { change.after_data = JSON.parse(e.target.value) } catch {} }">
          </textarea>
          <div class="hint">请输入 JSON 格式的变更后数据</div>
        </div>
        <div class="form-item full-width">
          <label>变更原因</label>
          <textarea v-model="(change as any).reason" class="input textarea" rows="2" placeholder="输入变更原因" maxlength="500"></textarea>
        </div>
      </div>

      <div class="form-actions">
        <button class="btn" @click="router.back()">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="handleSave">
          {{ saving ? '保存中...' : '保存' }}
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
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-item.full-width { grid-column: 1 / -1; }
.form-item label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
.input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.textarea { resize: vertical; font-family: inherit; }
select.input { background: #fff; }
.hint { font-size: 12px; color: #909399; margin-top: 4px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; padding-top: 16px; border-top: 1px solid #ebeef5; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
