<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { post } from '@/api'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const route = useRoute()
const router = useRouter()
const employeeId = Number(route.params.id)

const form = ref({
  hire_date: '',
  department: '',
  position: '',
  manager_name: '',
})
const saving = ref(false)
const error = ref('')

async function handleSubmit() {
  if (!form.value.hire_date) {
    error.value = '入职日期不能为空'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const res = await post(`/employees/${employeeId}/employments`, form.value)
    if (res.success) router.push(`/employees/${employeeId}`)
  } catch (e: any) {
    error.value = e.message || '创建失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <PageHeader title="新增任职记录" subtitle="为员工创建新的任职经历">
      <template #actions>
        <BaseButton variant="secondary" @click="router.back()">返回</BaseButton>
      </template>
    </PageHeader>

    <div class="card">
      <div v-if="error" class="error-msg">{{ error }}</div>

      <div class="form-group">
        <label>入职日期 <span class="required">*</span></label>
        <input v-model="form.hire_date" type="date" class="form-input" />
      </div>
      <div class="form-group">
        <label>部门</label>
        <input v-model="form.department" placeholder="可选" class="form-input" />
      </div>
      <div class="form-group">
        <label>岗位</label>
        <input v-model="form.position" placeholder="可选" class="form-input" />
      </div>
      <div class="form-group">
        <label>直属负责人</label>
        <input v-model="form.manager_name" placeholder="可选" class="form-input" />
      </div>

      <div class="form-actions">
        <button class="btn btn-cancel" @click="router.back()">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="handleSubmit">
          {{ saving ? '创建中...' : '创建' }}
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
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; }
.form-input:focus { outline: none; border-color: #409eff; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.btn { padding: 8px 20px; border: 1px solid #dcdfe6; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-primary:hover { background: #66b1ff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-cancel { background: #fff; color: #606266; }
.btn-cancel:hover { background: #f5f7fa; }
</style>
