<script setup lang="ts">
import { computed } from 'vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import type { IssueItem } from '@/types/roster-import'

const props = defineProps<{
  show: boolean
  issues: IssueItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

interface GroupSummary {
  actionText: string
  count: number
  autoFixable: number
  manualOnly: number
  updatesBusiness: number
  onlyStatus: number
}

const autoFixableIssues = computed(() => props.issues.filter(i => i.auto_fixable && i.resolution_status === 'PENDING'))
const manualOnlyIssues = computed(() => props.issues.filter(i => !i.auto_fixable && i.resolution_status === 'PENDING'))
const updatesBusinessCount = computed(() => autoFixableIssues.value.filter(i => i.requires_business_update).length)
const onlyStatusCount = computed(() => autoFixableIssues.value.filter(i => !i.requires_business_update).length)

const groups = computed<GroupSummary[]>(() => {
  const map: Record<string, GroupSummary> = {}
  for (const issue of props.issues) {
    if (issue.resolution_status !== 'PENDING') continue
    const code = issue.issue_code
    if (!map[code]) {
      map[code] = {
        actionText: issue.recommendation_text || issue.issue_code,
        count: 0,
        autoFixable: 0,
        manualOnly: 0,
        updatesBusiness: 0,
        onlyStatus: 0,
      }
    }
    map[code].count++
    if (issue.auto_fixable) {
      map[code].autoFixable++
      map[code].onlyStatus++
    } else {
      map[code].manualOnly++
    }
  }
  return Object.values(map)
})
</script>

<template>
  <BaseModal
    :show="show"
    title="批量处理预览"
    :message="''"
    :confirm-text="'确认处理'"
    :danger="false"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
  >
    <template #body>
      <div class="batch-preview">
        <div class="batch-stats">
          <div class="stat-item">
            <span class="stat-label">选中问题</span>
            <span class="stat-value">{{ issues.length }}条</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">可自动处理</span>
            <span class="stat-value auto">{{ autoFixableIssues.length }}条</span>
          </div>
          <div v-if="manualOnlyIssues.length > 0" class="stat-item">
            <span class="stat-label">需要人工处理</span>
            <span class="stat-value manual">{{ manualOnlyIssues.length }}条</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">会修改业务数据</span>
            <span class="stat-value warn">{{ updatesBusinessCount }}条</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">只更新问题状态</span>
            <span class="stat-value safe">{{ onlyStatusCount }}条</span>
          </div>
        </div>

        <div class="batch-groups">
          <div v-for="(group, idx) in groups" :key="idx" class="group-row">
            <span class="group-action">{{ group.actionText }}</span>
            <span class="group-count">{{ group.count }}条</span>
            <span v-if="group.autoFixable > 0" class="group-tag auto">可自动</span>
            <span v-if="group.manualOnly > 0" class="group-tag manual">需人工</span>
          </div>
        </div>
      </div>
    </template>
  </BaseModal>
</template>

<style scoped>
.batch-preview { padding: 0 4px; }
.batch-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-item { display: flex; flex-direction: column; align-items: center; padding: 12px; background: var(--color-bg); border-radius: var(--radius-md); }
.stat-label { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-bottom: 4px; }
.stat-value { font-size: var(--font-size-lg); font-weight: 700; }
.stat-value.auto { color: var(--color-success); }
.stat-value.manual { color: var(--color-warning); }
.stat-value.warn { color: var(--color-warning); }
.stat-value.safe { color: var(--color-primary); }
.batch-groups { max-height: 240px; overflow-y: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.group-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--color-border); }
.group-row:last-child { border-bottom: none; }
.group-action { flex: 1; font-size: var(--font-size-sm); }
.group-count { font-size: var(--font-size-xs); color: var(--color-text-secondary); min-width: 40px; text-align: right; }
.group-tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); font-weight: 500; }
.group-tag.auto { background: var(--color-success-soft); color: var(--color-success); }
.group-tag.manual { background: var(--color-warning-soft); color: var(--color-warning); }
</style>
