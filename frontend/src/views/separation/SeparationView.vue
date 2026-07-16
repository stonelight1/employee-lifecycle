<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '@/api'
import type { SeparationItem } from '@/types'
import { formatDate } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { employmentStatusMap, getStatusLabel } from '@/constants/status'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseModal from '@/components/base/BaseModal.vue'

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

const employmentId = Number(route.params.employmentId)
const preview = ref<any>(null)
const records = ref<SeparationItem[]>([])
const loading = ref(false)
const starting = ref(false)
const confirming = ref(false)

const separationType = ref('')
const reason = ref('')
const plannedDate = ref('')
const actualDate = ref('')
const hrComment = ref('')

async function loadData() {
  loading.value = true
  try {
    const [prevRes, recRes] = await Promise.all([
      get<any>(`/employments/${employmentId}/separation-preview`),
      get<{ items: SeparationItem[]; total: number }>(`/employments/${employmentId}/separation-records`),
    ])
    if (prevRes.success) preview.value = prevRes.data
    if (recRes.success && recRes.data) records.value = recRes.data.items
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  starting.value = true
  try {
    const res = await post(`/employments/${employmentId}/start-separation`, {
      planned_separation_date: plannedDate.value || null,
      separation_type: separationType.value || null,
      reason: reason.value || null,
      hr_comment: hrComment.value || null,
    })
    if (res.success) {
      showToast({ message: '离职流程已启动', type: 'success' })
      await loadData()
    }
  } catch (e: any) {
    showToast({ message: e.message || '启动失败', type: 'error' })
  } finally {
    starting.value = false
  }
}

async function doConfirm() {
  // Use custom confirm
  confirm({
    title: '确认离职',
    confirmText: '确认离职',
    danger: true,
    message: `确认该员工已于 ${actualDate.value || '所选日期'} 离职？\n\n该操作将：\n- 更新任职状态为"已离职"\n- 取消未完成的自动跟进任务\n- 关闭相关待办\n- 写入员工时间线和操作日志`,
    onConfirm: async () => {
      confirming.value = true
      try {
        const res = await post(`/employments/${employmentId}/confirm-separation`, {
          actual_separation_date: actualDate.value || null,
          hr_comment: hrComment.value || null,
          confirm: true,
        })
        if (res.success) {
          showToast({ message: '离职已确认', type: 'success' })
          await loadData()
        }
      } catch (e: any) {
        showToast({ message: e.message || '确认失败', type: 'error' })
      } finally {
        confirming.value = false
      }
    },
  })
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <div class="page-intro">
      <button class="back-link" @click="router.back()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        返回
      </button>
      <h1 class="page-title">离职管理</h1>
      <p class="page-subtitle">管理员工离职流程与记录</p>
    </div>

    <!-- 离职预览 -->
    <div class="card section-card" v-if="preview">
      <div class="section-title">离职预览</div>
      <div class="info-grid">
        <div class="info-item"><label>当前任职状态</label><span>{{ getStatusLabel(employmentStatusMap, preview.employment_status) }}</span></div>
        <div class="info-item"><label>入职日期</label><span>{{ formatDate(preview.hire_date) }}</span></div>
        <div class="info-item"><label>待处理任务数</label><span>{{ preview.pending_tasks_count ?? 0 }}</span></div>
        <div class="info-item"><label>待处理待办数</label><span>{{ preview.pending_todos_count ?? 0 }}</span></div>
      </div>

      <!-- 离职影响 -->
      <div v-if="(preview.pending_tasks_count || 0) + (preview.pending_todos_count || 0) > 0" class="impact-list">
        <div class="impact-item">
          <span class="impact-icon">⚠</span>
          <span>仍有 {{ preview.pending_tasks_count || 0 }} 项跟进任务未完成</span>
        </div>
        <div class="impact-item">
          <span class="impact-icon">⚠</span>
          <span>仍有 {{ preview.pending_todos_count || 0 }} 项待办未完成</span>
        </div>
      </div>
    </div>

    <!-- 启动离职 -->
    <div class="card section-card" v-if="preview?.can_start_separation && preview.employment_status !== 'SEPARATING' && preview.employment_status !== 'SEPARATED'">
      <div class="section-title">启动离职流程</div>
      <p class="text-sm text-tertiary mb-4" style="margin-bottom: 16px;">填写以下信息启动离职流程。</p>
      <div class="form-grid">
        <div class="form-item">
          <label>离职类型</label>
          <select v-model="separationType" class="input">
            <option value="">请选择</option>
            <option value="VOLUNTARY">主动离职</option>
            <option value="NEGOTIATED">协商解除</option>
            <option value="DISMISSAL">公司辞退</option>
            <option value="PROBATION_FAIL">试用期不通过</option>
            <option value="CONTRACT_EXPIRED">合同到期</option>
            <option value="OTHER">其他</option>
          </select>
        </div>
        <div class="form-item">
          <label>计划离职日期</label>
          <input v-model="plannedDate" type="date" class="input" />
        </div>
        <div class="form-item full-width">
          <label>离职原因</label>
          <textarea v-model="reason" class="input textarea" rows="3" placeholder="输入离职原因"></textarea>
        </div>
        <div class="form-item full-width">
          <label>HR 备注</label>
          <textarea v-model="hrComment" class="input textarea" rows="2" placeholder="HR 备注"></textarea>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn-primary" :disabled="starting" @click="handleStart">
          {{ starting ? '提交中...' : '启动离职流程' }}
        </button>
      </div>
    </div>

    <!-- 确认离职 -->
    <div class="card section-card" v-if="preview?.employment_status === 'SEPARATING'">
      <div class="section-title">确认离职</div>
      <div class="danger-zone">
        <p class="text-sm text-secondary mb-4" style="margin-bottom: 16px;">确认离职后，员工状态将变更为"已离职"，未完成任务将被取消。</p>
        <div class="form-grid" style="max-width: 400px;">
          <div class="form-item">
            <label>实际离职日期 <span class="text-danger">*</span></label>
            <input v-model="actualDate" type="date" class="input" />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-danger" :disabled="confirming || !actualDate" @click="doConfirm">
            {{ confirming ? '提交中...' : '确认离职' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 离职历史 -->
    <div class="card section-card">
      <div class="section-title">离职记录</div>
      <table v-if="records.length > 0" class="data-table">
        <thead>
          <tr>
            <th>离职类型</th>
            <th>原因</th>
            <th>计划日期</th>
            <th>实际日期</th>
            <th>确认人</th>
            <th>确认时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ r.separation_type || '-' }}</td>
            <td>{{ r.reason || '-' }}</td>
            <!-- 修复：计划日期使用 planned_separation_date -->
            <td>{{ formatDate(r.planned_separation_date) }}</td>
            <td>{{ formatDate(r.actual_separation_date) }}</td>
            <td>{{ r.confirmed_by || '-' }}</td>
            <td>{{ formatDate(r.confirmed_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty-state-inline text-tertiary">暂无离职记录</div>
    </div>

    <BaseModal
      :show="showConfirm"
      :title="confirmOpts.title"
      :message="confirmOpts.message"
      :confirm-text="confirmOpts.confirmText"
      :danger="confirmOpts.danger"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>

<style scoped>
.page-intro {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 20px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  width: fit-content;
}
.back-link:hover {
  color: var(--color-primary);
}
.section-card {
  padding: 20px;
  margin-bottom: 16px;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.info-item label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-bottom: 4px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-item.full-width { grid-column: 1 / -1; }
.form-item label {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-bottom: 4px;
}
.input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  outline: none;
}
.input:focus {
  border-color: var(--color-primary);
}
.textarea {
  resize: vertical;
  font-family: inherit;
}
select.input {
  background: var(--color-surface);
}
.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}
.btn-primary {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--color-danger);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
}
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.impact-list {
  margin-top: 12px;
}
.impact-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-warning-soft);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  font-size: var(--font-size-sm);
  color: var(--color-warning);
}
.impact-icon { flex-shrink: 0; }

.danger-zone {
  border: 1px solid var(--color-danger-soft);
  border-radius: var(--radius-sm);
  padding: 16px;
  background: var(--color-danger-soft);
}

/* Data table */
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.data-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }

.empty-state-inline {
  text-align: center;
  padding: 32px;
  font-size: var(--font-size-sm);
}
</style>
