<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import { ref, computed } from 'vue'
import { AlertTriangle, AlertCircle, Check } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import type { IssueItem } from '@/types/roster-import'

const props = defineProps<{
  issues: IssueItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  resolve: [issue: IssueItem, action: string]
  'modify-submit': [issue: IssueItem, value: string, note: string]
  continue: []
  prev: []
}>()

const blockerIssues = computed(() => props.issues.filter(i => i.severity === 'BLOCKER' && i.resolution_status === 'PENDING'))
const warningIssues = computed(() => props.issues.filter(i => i.severity === 'WARNING' && i.resolution_status === 'PENDING'))
const resolvedIssues = computed(() => props.issues.filter(i => i.resolution_status !== 'PENDING'))
const allBlockersResolved = computed(() => props.issues.filter(i => i.severity === 'BLOCKER').every(i => i.resolution_status !== 'PENDING'))

const editingIssueId = ref<number | null>(null)
const issueEditValue = ref('')
const issueEditNote = ref('')

const actionButtonInfo: Record<string, { label: string; variant: string }> = {
  accept: { label: '接受', variant: 'primary' },
  modify: { label: '修改', variant: 'secondary' },
  map: { label: '映射', variant: 'secondary' },
  create: { label: '新建', variant: 'primary' },
  skip: { label: '跳过此员工', variant: 'danger' },
  ignore: { label: '忽略', variant: 'ghost' },
  defer: { label: '稍后处理', variant: 'ghost' },
}

function startEdit(issue: IssueItem) {
  editingIssueId.value = issue.id
  issueEditValue.value = String(issue.new_value ?? '')
  issueEditNote.value = ''
}

function submitEdit(issue: IssueItem) {
  if (!issueEditValue.value.trim()) return
  emit('modify-submit', issue, issueEditValue.value, issueEditNote.value)
  editingIssueId.value = null
}

function cancelEdit() {
  editingIssueId.value = null
  issueEditValue.value = ''
  issueEditNote.value = ''
}
</script>

<template>
  <div class="step-content">
    <div class="card step-card">
      <h2 class="step-title">处理问题</h2>
      <p class="step-desc">阻断问题（BLOCKER）必须处理才能继续，提醒（WARNING）可以忽略或稍后处理。</p>

      <div v-if="blockerIssues.length > 0" class="issue-section">
        <h3 class="issue-section-title">
          <AlertCircle :size="16" class="issue-error-icon" />
          阻断问题（{{ blockerIssues.length }}）<span class="issue-hint">必须处理</span>
        </h3>
        <div v-for="issue in blockerIssues" :key="issue.id" class="issue-card issue-blocker">
          <div class="issue-header">
            <span class="issue-title">{{ issue.title }}</span>
            <BaseBadge type="custom" label="BLOCKER" color="#E11D48" background="#FFF1F2" size="sm" />
          </div>
          <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
          <div v-if="editingIssueId === issue.id" class="issue-edit-form">
            <div class="edit-field"><label>修改值</label><BaseInput v-model="issueEditValue" placeholder="输入新值" /></div>
            <div class="edit-field"><label>备注</label><BaseInput v-model="issueEditNote" placeholder="修改原因" /></div>
            <div class="edit-actions"><BaseButton variant="ghost" size="sm" @click="cancelEdit">取消</BaseButton><BaseButton variant="primary" size="sm" @click="submitEdit(issue)">保存</BaseButton></div>
          </div>
          <div v-else class="issue-actions">
            <button v-for="action in issue.allowed_actions" :key="action"
              :class="['issue-action-btn', actionButtonInfo[action]?.variant || 'secondary']"
              @click="action === 'modify' ? startEdit(issue) : emit('resolve', issue, action)">
              {{ actionButtonInfo[action]?.label || action }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="warningIssues.length > 0" class="issue-section">
        <h3 class="issue-section-title">
          <AlertTriangle :size="16" class="issue-warn-icon" />
          提醒（{{ warningIssues.length }}）<span class="issue-hint">可以忽略</span>
        </h3>
        <div v-for="issue in warningIssues" :key="issue.id" class="issue-card issue-warning">
          <div class="issue-header">
            <span class="issue-title">{{ issue.title }}</span>
            <BaseBadge type="custom" label="WARNING" color="#D97706" background="#FFF7E8" size="sm" />
          </div>
          <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
          <div v-if="editingIssueId === issue.id" class="issue-edit-form">
            <div class="edit-field"><label>修改值</label><BaseInput v-model="issueEditValue" placeholder="输入新值" /></div>
            <div class="edit-field"><label>备注</label><BaseInput v-model="issueEditNote" placeholder="修改原因" /></div>
            <div class="edit-actions"><BaseButton variant="ghost" size="sm" @click="cancelEdit">取消</BaseButton><BaseButton variant="primary" size="sm" @click="submitEdit(issue)">保存</BaseButton></div>
          </div>
          <div v-else class="issue-actions">
            <button v-for="action in issue.allowed_actions" :key="action"
              :class="['issue-action-btn', actionButtonInfo[action]?.variant || 'secondary']"
              @click="action === 'modify' ? startEdit(issue) : emit('resolve', issue, action)">
              {{ actionButtonInfo[action]?.label || action }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="resolvedIssues.length > 0" class="issue-section">
        <h3 class="issue-section-title"><Check :size="16" class="issue-resolved-icon" />已处理（{{ resolvedIssues.length }}）</h3>
        <div v-for="issue in resolvedIssues" :key="issue.id" class="issue-card issue-resolved">
          <div class="issue-header">
            <span class="issue-title">{{ issue.title }}</span>
            <span class="resolved-label">{{ issue.resolution_action === 'ignore' ? '已忽略' : '已解决' }}</span>
          </div>
        </div>
      </div>

      <div v-if="blockerIssues.length === 0 && warningIssues.length === 0 && resolvedIssues.length === 0">
        <BaseEmpty title="没有问题" description="所有数据正常" />
      </div>

      <div class="form-actions">
        <BaseButton variant="ghost" @click="emit('prev')">上一步</BaseButton>
        <BaseButton variant="primary" :disabled="!allBlockersResolved" @click="emit('continue')">继续 <ChevronRight :size="16" /></BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.step-card { padding: 28px 32px; }
.step-title { font-size: var(--font-size-md); font-weight: 700; margin-bottom: 4px; }
.step-desc { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin-bottom: 20px; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.issue-section { margin-bottom: 24px; }
.issue-section-title { display: flex; align-items: center; gap: 8px; font-size: var(--font-size-base); font-weight: 600; margin-bottom: 12px; }
.issue-error-icon { color: var(--color-danger); }
.issue-warn-icon { color: var(--color-warning); }
.issue-resolved-icon { color: var(--color-success); }
.issue-hint { font-size: var(--font-size-xs); font-weight: 400; color: var(--color-text-tertiary); }
.issue-card { padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); margin-bottom: 10px; }
.issue-blocker { border-left: 3px solid var(--color-danger); }
.issue-warning { border-left: 3px solid var(--color-warning); }
.issue-resolved { border-left: 3px solid var(--color-success); opacity: 0.7; }
.issue-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 8px; }
.issue-title { font-size: var(--font-size-sm); font-weight: 500; }
.issue-message { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-bottom: 8px; }
.issue-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.issue-action-btn { padding: 4px 12px; border-radius: var(--radius-sm); font-size: var(--font-size-xs); font-weight: 500; cursor: pointer; border: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-text-primary); }
.issue-action-btn:hover { background: var(--color-bg); }
.issue-action-btn.primary { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.issue-action-btn.danger { color: var(--color-danger); border-color: var(--color-danger-soft); background: var(--color-danger-soft); }
.issue-action-btn.ghost { border-color: transparent; background: transparent; }
.resolved-label { font-size: var(--font-size-xs); color: var(--color-success); font-weight: 500; }
.issue-edit-form { margin-top: 10px; padding: 12px; background: var(--color-bg); border-radius: var(--radius-sm); display: flex; flex-direction: column; gap: 10px; }
.edit-field label { display: block; font-size: var(--font-size-xs); font-weight: 500; margin-bottom: 4px; color: var(--color-text-secondary); }
.edit-actions { display: flex; gap: 6px; justify-content: flex-end; }
</style>
