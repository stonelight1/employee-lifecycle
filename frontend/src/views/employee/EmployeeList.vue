<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get, del } from '@/api'
import type { EmployeeItem } from '@/types'

const router = useRouter()
const employees = ref<EmployeeItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const searchName = ref('')

async function loadEmployees() {
  loading.value = true
  try {
    const res = await get<{ items: EmployeeItem[]; total: number }>('/employees', {
      page: page.value,
      page_size: pageSize,
      name: searchName.value || undefined,
    })
    if (res.success && res.data) {
      employees.value = res.data.items
      total.value = res.data.total
    }
  } catch (e: any) {
    console.error('加载员工列表失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  if (!confirm('确认删除该员工？')) return
  try {
    await del(`/employees/${id}`)
    await loadEmployees()
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

onMounted(loadEmployees)
</script>

<template>
  <div class="employee-list">
    <div class="toolbar">
      <input v-model="searchName" placeholder="搜索员工姓名" class="search-input" @input="loadEmployees" />
      <button class="btn btn-primary" @click="router.push('/employees/new')">新增员工</button>
    </div>

    <div class="table-card">
      <table v-if="employees.length > 0">
        <thead>
          <tr>
            <th>姓名</th>
            <th>员工编号</th>
            <th>手机号</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="emp in employees" :key="emp.id">
            <td>
              <a class="link" @click="router.push(`/employees/${emp.id}`)">{{ emp.name }}</a>
            </td>
            <td>{{ emp.employee_no || '-' }}</td>
            <td>{{ emp.mobile || '-' }}</td>
            <td>
              <span class="tag" :class="emp.employee_status === 'ACTIVE' ? 'tag-green' : 'tag-gray'">
                {{ emp.employee_status === 'ACTIVE' ? '在职' : '已归档' }}
              </span>
            </td>
            <td>{{ emp.created_at?.slice(0, 10) }}</td>
            <td>
              <button class="btn btn-sm" @click="router.push(`/employees/${emp.id}`)">查看</button>
              <button class="btn btn-sm btn-danger" @click="handleDelete(emp.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">暂无员工数据</div>
      <div v-else class="empty">加载中...</div>
    </div>

    <div class="pagination" v-if="total > pageSize">
      <button :disabled="page <= 1" @click="page--; loadEmployees()">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; loadEmployees()">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}
.search-input {
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  width: 240px;
  font-size: 14px;
}
.table-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #ebeef5;
  font-size: 14px;
}
th {
  background: #fafafa;
  font-weight: 600;
  color: #606266;
}
.link {
  color: #409eff;
  cursor: pointer;
}
.link:hover {
  text-decoration: underline;
}
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.tag-green {
  background: #e1f3d8;
  color: #67c23a;
}
.tag-gray {
  background: #f4f4f5;
  color: #909399;
}
.btn {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}
.btn-primary {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}
.btn-primary:hover {
  background: #66b1ff;
}
.btn-sm {
  padding: 4px 10px;
  margin-right: 4px;
  font-size: 12px;
}
.btn-danger {
  color: #f56c6c;
  border-color: #f56c6c;
}
.btn-danger:hover {
  background: #fef0f0;
}
.empty {
  text-align: center;
  padding: 48px;
  color: #909399;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
