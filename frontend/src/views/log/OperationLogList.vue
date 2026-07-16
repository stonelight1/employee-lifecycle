<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { get } from '@/api'
import type { LogItem } from '@/types'

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
  <div>
    <div class="page-header">
      <h2>操作日志</h2>
    </div>
    <div class="table-card">
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
            <td>{{ log.operated_at?.slice(0, 19) }}</td>
            <td>{{ log.object_type }}</td>
            <td>{{ log.operation_type }}</td>
            <td>{{ log.operation_source || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">{{ loading ? '加载中...' : '暂无操作日志' }}</div>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 16px; }
.table-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
