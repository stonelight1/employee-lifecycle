<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post, patch, del as delReq } from '@/api'
import type { EmployeeItem, EmploymentItem } from '@/types'

const route = useRoute()
const router = useRouter()
const employeeId = Number(route.params.id)

const employee = ref<EmployeeItem | null>(null)
const employments = ref<EmploymentItem[]>([])
const activeTab = ref('info')

onMounted(async () => {
  try {
    const empRes = await get<EmployeeItem>(`/employees/${employeeId}`)
    if (empRes.success) employee.value = empRes.data!

    const empListRes = await get<any>(`/employees/${employeeId}/employments`)
    // 任职列表在 empployments 中关联查询
  } catch (e: any) {
    console.error(e)
  }
})

async function handleDelete() {
  if (!confirm('确认删除此员工？')) return
  try {
    await delReq(`/employees/${employeeId}`)
    router.push('/employees')
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div v-if="employee" class="detail">
    <div class="detail-header">
      <button class="btn-back" @click="router.push('/employees')">← 返回</button>
      <h2>{{ employee.name }}</h2>
      <span class="tag" :class="employee.employee_status === 'ACTIVE' ? 'tag-green' : 'tag-gray'">
        {{ employee.employee_status === 'ACTIVE' ? '在职' : '已归档' }}
      </span>
      <div class="header-actions">
        <button class="btn btn-primary" @click="router.push(`/employees/${employeeId}/edit`)">编辑</button>
        <button class="btn btn-danger" @click="handleDelete">删除</button>
      </div>
    </div>

    <div class="detail-body">
      <div class="tabs">
        <div class="tab" :class="{ active: activeTab === 'info' }" @click="activeTab = 'info'">基本信息</div>
        <div class="tab" :class="{ active: activeTab === 'employment' }" @click="activeTab = 'employment'">任职记录</div>
        <div class="tab" :class="{ active: activeTab === 'timeline' }" @click="activeTab = 'timeline'">时间线</div>
      </div>

      <div v-if="activeTab === 'info'" class="tab-content">
        <div class="info-grid">
          <div class="info-item"><label>员工编号</label><span>{{ employee.employee_no || '-' }}</span></div>
          <div class="info-item"><label>姓名</label><span>{{ employee.name }}</span></div>
          <div class="info-item"><label>手机号</label><span>{{ employee.mobile || '-' }}</span></div>
          <div class="info-item"><label>邮箱</label><span>{{ employee.email || '-' }}</span></div>
          <div class="info-item"><label>状态</label><span>{{ employee.employee_status }}</span></div>
          <div class="info-item"><label>创建时间</label><span>{{ employee.created_at }}</span></div>
        </div>
      </div>

      <div v-if="activeTab === 'employment'" class="tab-content">
        <button class="btn btn-primary" @click="router.push(`/employees/${employeeId}/employments/new`)">新增任职</button>
        <div v-if="employments.length === 0" class="empty">暂无任职记录</div>
        <div v-for="emp in employments" :key="emp.id" class="employment-card">
          <div>入职日期: {{ emp.hire_date }}</div>
          <div>状态: {{ emp.employment_status }}</div>
          <div>部门: {{ emp.department || '-' }}</div>
          <div>岗位: {{ emp.position || '-' }}</div>
          <button @click="router.push(`/employees/${employeeId}/employments/${emp.id}`)">查看详情</button>
        </div>
      </div>

      <div v-if="activeTab === 'timeline'" class="tab-content">
        <div class="empty">时间线功能开发中</div>
      </div>
    </div>
  </div>
  <div v-else class="loading">加载中...</div>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  background: #fff;
  padding: 16px 24px;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.btn-back {
  background: none;
  border: none;
  cursor: pointer;
  color: #409eff;
  font-size: 14px;
}
.header-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.tabs {
  display: flex;
  gap: 0;
  background: #fff;
  border-radius: 8px 8px 0 0;
  overflow: hidden;
}
.tab {
  padding: 12px 24px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font-size: 14px;
}
.tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
}
.tab-content {
  background: #fff;
  padding: 24px;
  border-radius: 0 0 8px 8px;
  min-height: 200px;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.info-item label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.employment-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 16px;
  margin-top: 12px;
}
.loading, .empty {
  text-align: center;
  padding: 48px;
  color: #909399;
}
</style>
