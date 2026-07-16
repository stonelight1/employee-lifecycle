<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '@/api'
import type { LogItem } from '@/types'
import { formatDateTime } from '@/utils/date'

const logs = ref<LogItem[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)

onMounted(async () => {
  loading.value = true
  try {
    const res = await get<{ items: LogItem[]; total: number }>('/operation-logs', { page: page.value, page_size: 20 })
    if (res.success) {
      logs.value = res.data?.items || []
      total.value = res.data?.total || 0
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">操作日志</h1>
      <p class="page-subtitle">系统操作审计记录</p>
    </div>
    <div class="card table-card">
      <table v-if="logs.length > 0">
        <thead>
          <tr>
            <th>操作人</th>
            <th>操作时间</th>
            <th>对象类型</th>
            <th>操作类型</th>
            <th>来源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td>{{ log.operator_id }}</td>
            <td>{{ formatDateTime(log.operated_at) }}</td>
            <td>{{ log.object_type }}</td>
            <td><code class="code-tag">{{ log.operation_type }}</code></td>
            <td>{{ log.operation_source || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline">暂无操作日志</div>
      <div v-else class="empty-state-inline">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.page-intro { margin-bottom: 20px; }
.table-card { overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.code-tag { font-family: monospace; font-size: var(--font-size-xs); background: var(--color-bg); padding: 2px 6px; border-radius: 4px; }
.empty-state-inline { text-align: center; padding: 48px; color: var(--color-text-tertiary); }
</style>
