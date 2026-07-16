<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get, post } from '@/api'
import type { TodoItem } from '@/types'
import { formatDate, formatRelativeDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import PageHeader from '@/components/layout/PageHeader.vue'
import { getStatusLabel, todoStatusMap } from '@/constants/status'

const { showToast } = useToast()
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
    showToast({ message: '待办已完成', type: 'success' })
  } catch (e: any) {
    showToast({ message: e.message || '操作失败', type: 'error' })
  }
}
</script>

<template>
  <div class="page">
    <PageHeader title="待办事项" subtitle="管理需要处理的待办事项" />
    <div class="card table-card">
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
            <td><span class="todo-title">{{ todo.title }}</span></td>
            <td>{{ todo.business_type }}</td>
            <td>{{ todo.due_at ? `${formatDate(todo.due_at)} (${formatRelativeDate(todo.due_at)})` : '—' }}</td>
            <td>{{ todo.priority || '普通' }}</td>
            <td>
              <button class="complete-btn" @click="handleComplete(todo.id)">完成</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline">暂无待办事项</div>
      <div v-else class="empty-state-inline">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.table-card { overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.todo-title { font-weight: 500; }
.complete-btn { padding: 4px 12px; border: 1px solid var(--color-primary); border-radius: var(--radius-sm); background: var(--color-primary-soft); color: var(--color-primary); font-size: var(--font-size-xs); cursor: pointer; }
.complete-btn:hover { background: var(--color-primary); color: #fff; }
.empty-state-inline { text-align: center; padding: 48px; color: var(--color-text-tertiary); }
</style>
