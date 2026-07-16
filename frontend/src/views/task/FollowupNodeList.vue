<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'

const router = useRouter()
const nodes = ref<any[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await get<{ items: any[]; total: number }>('/followup-nodes')
    if (res.success) nodes.value = res.data?.items || []
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
      <h2>跟进节点配置</h2>
    </div>
    <div class="table-card">
      <table v-if="nodes.length > 0">
        <thead>
          <tr>
            <th>节点名称</th>
            <th>编码</th>
            <th>偏移天数</th>
            <th>确认模式</th>
            <th>启用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="node in nodes" :key="node.id">
            <td>{{ node.node_name }}</td>
            <td>{{ node.node_code }}</td>
            <td>{{ node.offset_days ?? '-' }}</td>
            <td>{{ node.confirmation_mode }}</td>
            <td>{{ node.enabled ? '✅' : '❌' }}</td>
            <td>
              <button class="btn btn-sm">编辑</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">{{ loading ? '加载中...' : '暂无节点配置' }}</div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; margin-bottom: 16px; }
.table-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.btn-sm { padding: 4px 10px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 12px; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
