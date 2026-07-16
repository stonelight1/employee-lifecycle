<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '@/api'
import { formatDate } from '@/utils/date'
import { changeTypeMap, separationTypeMap, getStatusLabel } from '@/constants/status'
import ChangeDiffPanel from '@/components/business/ChangeDiffPanel.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'

const router = useRouter()
const changes = ref<any[]>([])
const separations = ref<any[]>([])
const loading = ref(true)
const activeTab = ref<'changes' | 'separation'>('changes')

async function loadData() {
  loading.value = true
  try {
    // 使用聚合接口
    const res = await get<{ changes: any[]; separations: any[] }>('/employee-movements')
    if (res.success && res.data) {
      changes.value = res.data.changes || []
      separations.value = res.data.separations || []
    }
  } catch (e: any) {
    console.error('加载异动离职数据失败:', e)
    // 降级：直接使用旧方式
    try {
      await loadDataFallback()
    } catch (fallbackErr) {
      console.error('降级加载也失败:', fallbackErr)
    }
  } finally {
    loading.value = false
  }
}

async function loadDataFallback() {
  const empRes = await get<{ items: any[]; total: number }>('/employees', { page: 1, page_size: 100 })
  const shifts: any[] = []
  const seps: any[] = []

  if (empRes.success && empRes.data) {
    for (const emp of empRes.data.items) {
      const empListRes = await get<{ items: any[]; total: number }>(`/employees/${emp.id}/employments`)
      const employments = empListRes.data?.items || []
      for (const e of employments) {
        try {
          const chRes = await get<{ items: any[] }>(`/employments/${e.id}/changes`)
          if (chRes.data?.items) {
            for (const c of chRes.data.items) {
              shifts.push({
                ...c,
                employee_name: emp.name,
                department: e.department,
                position: e.position,
                employment_id: e.id,
                employee_id: emp.id,
              })
            }
          }
        } catch {}
        try {
          const sepRes = await get<{ items: any[] }>(`/employments/${e.id}/separation-records`)
          if (sepRes.data?.items) {
            for (const s of sepRes.data.items) {
              seps.push({
                ...s,
                employee_name: emp.name,
                department: e.department,
                position: e.position,
                employment_id: e.id,
                employee_id: emp.id,
              })
            }
          }
        } catch {}
      }
    }
  }
  changes.value = shifts
  separations.value = seps
}

function parseChangeData(data: any): Record<string, any> | null {
  if (!data) return null
  if (typeof data === 'string') {
    try { return JSON.parse(data) } catch { return null }
  }
  if (typeof data === 'object') return data
  return null
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <h1 class="page-title">异动与离职</h1>
      <p class="page-subtitle">查看员工的异动记录和离职流程</p>
    </div>

    <div class="tabs-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'changes' }" @click="activeTab = 'changes'">
        异动记录 ({{ changes.length }})
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'separation' }" @click="activeTab = 'separation'">
        离职记录 ({{ separations.length }})
      </button>
    </div>

    <div v-if="loading" class="loading-state text-tertiary">加载中...</div>

    <!-- 异动记录 -->
    <div v-else-if="activeTab === 'changes'">
      <div v-if="changes.length === 0">
        <BaseEmpty title="暂无异动记录" description="员工异动信息将显示在这里" />
      </div>
      <div v-else class="table-card card">
        <table>
          <thead>
            <tr>
              <th>员工</th>
              <th>异动类型</th>
              <th>变更详情</th>
              <th>生效日期</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in changes" :key="c.id">
              <td>
                <span class="link" @click="router.push(`/employees/${c.employee_id}`)">{{ c.employee_name }}</span>
                <div class="text-xs text-tertiary">{{ c.department }} · {{ c.position }}</div>
              </td>
              <td>{{ getStatusLabel(changeTypeMap, c.change_type) }}</td>
              <td class="diff-cell">
                <ChangeDiffPanel
                  :before-data="parseChangeData(c.before_data)"
                  :after-data="parseChangeData(c.after_data)"
                />
              </td>
              <td>{{ c.effective_date || '-' }}</td>
              <td>
                <button class="table-btn" @click="router.push(`/employments/${c.employment_id}/changes`)">查看</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 离职记录 -->
    <div v-else>
      <div v-if="separations.length === 0">
        <BaseEmpty title="暂无离职记录" />
      </div>
      <div v-else class="table-card card">
        <table>
          <thead>
            <tr>
              <th>员工</th>
              <th>类型</th>
              <th>计划日期</th>
              <th>实际日期</th>
              <th>原因</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in separations" :key="s.id">
              <td>
                <span class="link" @click="router.push(`/employees/${s.employee_id}`)">{{ s.employee_name }}</span>
                <div class="text-xs text-tertiary">{{ s.department }} · {{ s.position }}</div>
              </td>
              <td>{{ getStatusLabel(separationTypeMap, s.separation_type) }}</td>
              <td>{{ s.planned_separation_date || '-' }}</td>
              <td>{{ s.actual_separation_date || '-' }}</td>
              <td class="data-cell">{{ s.reason || '-' }}</td>
              <td>
                <button class="table-btn" @click="router.push(`/employments/${s.employment_id}/separation`)">查看</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-intro {
  margin-bottom: 20px;
}
.tabs-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.tab-btn {
  padding: 8px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.tab-btn.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.table-card {
  overflow: hidden;
}
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.diff-cell { max-width: 250px; }
.data-cell { max-width: 150px; font-size: var(--font-size-xs); }
.link { color: var(--color-primary); cursor: pointer; }
.table-btn { padding: 3px 10px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-surface); cursor: pointer; font-size: var(--font-size-xs); }
</style>
