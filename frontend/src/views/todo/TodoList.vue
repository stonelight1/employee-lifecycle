<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get, post } from '@/api'
import type { TodoItem } from '@/types'

const todos = ref<TodoItem[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await get<{ items: TodoItem[]; total: number }>('/todos', { page: 1, page_size: 100 })
    if (res.success) todos.value = res.data?.items || []
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

async function handleComplete(id: number) {
  try {
    await post(`/todos/${id}/complete`)
    todos.value = todos.value.filter((t) => t.id !== id)
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>待办事项</h2>
    </div>
    <div class="table-card">
      <table v-if="todos.length > 0">
        <thead>
          <tr>
            <th>标题</th>
            <th>业务类型</th>
            <th>截止日期</th>
            <th>优先级</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="todo in todos" :key="todo.id">
            <td>{{ todo.title }}</td>
            <td>{{ todo.business_type }}</td>
            <td>{{ todo.due_at || '-' }}</td>
            <td>{{ todo.priority || '普通' }}</td>
            <td>
              <button class="btn btn-sm btn-primary" @click="handleComplete(todo.id)">完成</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">{{ loading ? '加载中...' : '暂无待办事项' }}</div>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 16px; }
.table-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.btn-sm { padding: 4px 10px; border: 1px solid #dcdfe6; border-radius: 6px; cursor: pointer; font-size: 12px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
