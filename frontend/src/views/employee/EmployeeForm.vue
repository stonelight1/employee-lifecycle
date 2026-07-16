<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch } from '@/api'
import type { EmployeeItem } from '@/types'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const route = useRoute()
const router = useRouter()
const isEdit = route.name === 'EmployeeEdit'
const employeeId = isEdit ? Number(route.params.id) : null

const form = ref({
  name: '',
  employee_no: '',
  mobile: '',
  email: '',
  source: '',
})
const saving = ref(false)
const error = ref('')

onMounted(async () => {
  if (isEdit && employeeId) {
    try {
      const res = await get<EmployeeItem>(`/employees/${employeeId}`)
      if (res.success && res.data) {
        form.value.name = res.data.name
        form.value.employee_no = res.data.employee_no || ''
        form.value.mobile = res.data.mobile || ''
        form.value.email = res.data.email || ''
        form.value.source = res.data.source || ''
      }
    } catch (e: any) {
      error.value = e.message || '加载员工信息失败'
    }
  }
})

async function handleSubmit() {
  if (!form.value.name.trim()) {
    error.value = '员工姓名不能为空'
    return
  }
  saving.value = true
  error.value = ''
  try {
    if (isEdit && employeeId) {
      const res = await patch(`/employees/${employeeId}`, form.value)
      if (res.success) router.push(`/employees/${employeeId}`)
    } else {
      const res = await post('/employees', form.value)
      if (res.success) router.push(`/employees/${(res.data as any).id}`)
    }
  } catch (e: any) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <PageHeader :title="isEdit ? '编辑员工' : '新增员工'" subtitle="维护员工基础档案信息">
      <template #actions>
        <BaseButton variant="secondary" @click="router.back()">返回</BaseButton>
      </template>
    </PageHeader>

    <div class="card">
      <div v-if="error" class="error-msg">{{ error }}</div>

      <div class="form-group">
        <label>姓名 <span class="required">*</span></label>
        <input v-model="form.name" placeholder="请输入员工姓名" class="form-input" />
      </div>
      <div class="form-group">
        <label>员工编号</label>
        <input v-model="form.employee_no" placeholder="可选" class="form-input" />
      </div>
      <div class="form-group">
        <label>手机号</label>
        <input v-model="form.mobile" placeholder="可选" class="form-input" />
      </div>
      <div class="form-group">
        <label>邮箱</label>
        <input v-model="form.email" placeholder="可选" class="form-input" />
      </div>
      <div class="form-group">
        <label>来源</label>
        <input v-model="form.source" placeholder="可选" class="form-input" />
      </div>

      <div class="form-actions">
        <button class="btn btn-cancel" @click="router.back()">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="handleSubmit">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); max-width: 600px; }
.error-msg { background: #fef0f0; color: #f56c6c; padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 14px; color: #606266; margin-bottom: 6px; font-weight: 500; }
.required { color: #f56c6c; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; transition: border-color 0.2s; }
.form-input:focus { outline: none; border-color: #409eff; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.btn { padding: 8px 20px; border: 1px solid #dcdfe6; border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.2s; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-primary:hover { background: #66b1ff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-cancel { background: #fff; color: #606266; }
.btn-cancel:hover { background: #f5f7fa; }
</style>
