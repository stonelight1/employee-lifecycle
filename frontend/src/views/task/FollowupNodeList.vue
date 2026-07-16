<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { confirmationModeMap, getStatusLabel } from '@/constants/status'
import PageHeader from '@/components/layout/PageHeader.vue'

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
  <div class="page">
    <PageHeader title="节点配置" subtitle="配置员工跟进节点和流程" />

    <div class="card table-card">
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
            <td><strong>{{ node.node_name }}</strong></td>
            <td><code class="code">{{ node.node_code }}</code></td>
            <td>{{ node.offset_days != null ? `${node.offset_days} 天` : '—' }}</td>
            <td>{{ getStatusLabel(confirmationModeMap, node.confirmation_mode) }}</td>
            <td>
              <span v-if="node.enabled" class="toggle-dot active" />
              <span v-else class="toggle-dot" />
              <span class="text-xs text-tertiary" style="margin-left: 4px;">{{ node.enabled ? '启用' : '禁用' }}</span>
            </td>
            <td>
              <button class="table-btn">编辑</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline">暂无节点配置</div>
    </div>
  </div>
</template>

<style scoped>

.table-card {
  overflow: hidden;
}
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.code { font-family: monospace; font-size: var(--font-size-xs); background: var(--color-bg); padding: 2px 6px; border-radius: 4px; }
.toggle-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
}
.toggle-dot.active {
  background: var(--color-success);
}
.table-btn { padding: 3px 10px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); cursor: pointer; font-size: var(--font-size-xs); }
.empty-state-inline { text-align: center; padding: 48px; color: var(--color-text-tertiary); font-size: var(--font-size-sm); }
</style>
