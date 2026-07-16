<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get } from '@/api'
import type { EmploymentChangeItem } from '@/types'
import PageHeader from '@/components/layout/PageHeader.vue'
import BaseButton from '@/components/base/BaseButton.vue'

const route = useRoute()
const router = useRouter()
const employmentId = Number(route.params.employmentId)

const changes = ref<EmploymentChangeItem[]>([])
const loading = ref(false)

async function loadChanges() {
  loading.value = true
  try {
    const res = await get<{ items: EmploymentChangeItem[]; total: number }>(`/employments/${employmentId}/changes`)
    if (res.success && res.data) {
      changes.value = res.data.items
    }
  } catch (e: any) {
    console.error('加载异动记录失败:', e)
  } finally {
    loading.value = false
  }
}

function parseData(data: string | Record<string, any> | undefined): string {
  if (!data) return '-'
  if (typeof data === 'string') {
    try { return JSON.stringify(JSON.parse(data), null, 1) } catch { return data }
  }
  return JSON.stringify(data, null, 1)
}

const changeTypeLabels: Record<string, string> = {
  DEPARTMENT: '部门变更',
  POSITION: '岗位变更',
  MANAGER: '负责人变更',
}

onMounted(loadChanges)
</script>

<template>
  <div class="page">
    <PageHeader title="异动记录" subtitle="查看并维护员工任职异动历史">
      <template #actions>
        <BaseButton variant="secondary" @click="router.back()">返回</BaseButton>
        <BaseButton variant="primary" @click="router.push(`/employments/${employmentId}/changes/create`)">新增异动</BaseButton>
      </template>
    </PageHeader>

    <div class="card">
      <table v-if="changes.length > 0">
        <thead>
          <tr>
            <th>类型</th>
            <th>生效日期</th>
            <th>变更前</th>
            <th>变更后</th>
            <th>原因</th>
            <th>确认人</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in changes" :key="c.id">
            <td><span class="tag tag-blue">{{ changeTypeLabels[c.change_type] || c.change_type }}</span></td>
            <td>{{ c.effective_date }}</td>
            <td class="data-cell">{{ parseData(c.before_data) }}</td>
            <td class="data-cell">{{ parseData(c.after_data) }}</td>
            <td>{{ c.reason || '-' }}</td>
            <td>{{ c.confirmed_by || '-' }}</td>
            <td>
              <button class="btn btn-sm" @click="router.push(`/employment-changes/${c.id}?employment_id=${employmentId}`)">编辑</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">暂无异动记录</div>
      <div v-else class="empty">加载中...</div>
    </div>
  </div>
</template>

<style scoped>
.card { background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06); overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 14px; }
th { background: #fafafa; font-weight: 600; color: #606266; }
.data-cell { max-width: 200px; white-space: pre-wrap; font-size: 12px; color: #606266; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #f4f4f5; color: #909399; }
.tag-blue { background: #d9ecff; color: #409eff; }
.btn { padding: 6px 16px; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; cursor: pointer; font-size: 14px; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-sm { padding: 4px 10px; margin-right: 4px; font-size: 12px; }
.empty { text-align: center; padding: 48px; color: #909399; }
</style>
