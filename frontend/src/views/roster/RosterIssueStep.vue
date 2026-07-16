<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ChevronDown, ChevronRight, AlertTriangle, AlertCircle, Check, Search, X } from 'lucide-vue-next'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import type { IssueItem } from '@/types/roster-import'
import RosterIssueEditDrawer from './RosterIssueEditDrawer.vue'
import RosterBatchResolveDialog from './RosterBatchResolveDialog.vue'

const props = defineProps<{
  issues: IssueItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  resolve: [issue: IssueItem, action: string]
  'modify-submit': [issue: IssueItem, value: string, note: string]
  'batch-resolve': [issueIds: number[], action: string]
  continue: []
  prev: []
}>()

// ===================== 筛选状态 =====================
const severityFilter = ref<string>('ALL')
const statusFilter = ref<string>('ALL')
const issueCodeFilter = ref<string>('ALL')
const searchText = ref('')

// ===================== 计算属性 =====================
const pendingIssues = computed(() => props.issues.filter(i => i.resolution_status === 'PENDING'))
const resolvedIssues = computed(() => props.issues.filter(i => i.resolution_status !== 'PENDING'))
const allBlockersResolved = computed(() => props.issues.filter(i => i.severity === 'BLOCKER').every(i => i.resolution_status !== 'PENDING'))

// 可用的问题类型筛选选项
const issueCodeOptions = computed(() => {
  const codes = new Set(props.issues.map(i => i.issue_code))
  return Array.from(codes).sort()
})

// issue_code 中文映射
const issueCodeLabels: Record<string, string> = {
  WORK_AGE_MISMATCH: '工龄不符',
  AGE_MISMATCH: '年龄不符',
  MISSING_HIRE_DATE: '缺少入职日期',
  MISSING_REGULARIZATION_DATE: '缺少转正日期',
  EMPLOYMENT_FORM_REGULARIZATION_CONFLICT: '用工形式冲突',
  MISSING_REQUIRED_FIELD: '缺少必填字段',
  NAME_EMPTY: '姓名为空',
  DUPLICATE_NAME_IN_EXCEL: 'Excel重复姓名',
  MULTIPLE_DB_MATCH: '数据库多条匹配',
  INACTIVE_EMPLOYEE: '员工记录非活跃',
  REHIRE_SCENARIO: '重新入职',
  INVALID_PROBATION_MONTHS: '试用期月数不合法',
  SALARY_UNPARSABLE: '薪酬文本无法解析',
  PDP_CONTENT_SUSPICIOUS: 'PDP测评异常',
  BENEFIT_TEXT_UNRECOGNIZED: '五险一金无法识别',
  REGION_COOPERATION: '合作地区跳过',
  FROM_REGULARIZATION_DATE: '社保转正缴纳',
  FROM_HIRE_DATE: '社保入职缴纳',
  AFTER_PROBATION: '试用期后缴纳',
  SOCIAL_INSURANCE_FULL: '全额缴纳',
  SOCIAL_INSURANCE_MIN: '最低基数',
  SOCIAL_INSURANCE_CUSTOM: '自定义基数',
  CONTRACT_CHANGE: '合同变更',
  NEW_BANK_ACCOUNT: '新银行卡号',
  NEW_ALIPAY_ACCOUNT: '新支付宝账号',
  POSSIBLE_REEMPLOYMENT: '可能再次入职',
  PENDING_SEPARATION: '待离职',
  IDENTITY_BIRTH_DATE_CONFLICT: '身份证生日冲突',
  GENDER_IDENTITY_CONFLICT: '性别冲突',
  EMPLOYEE_MATCH_CONFLICT: '员工匹配冲突',
  DUPLICATE_EMPLOYEE_NAME: '重名员工',
  NEW_DEPARTMENT: '新部门',
  NEW_POSITION: '新岗位',
  NEW_TEAM: '新团队',
  UNKNOWN_BENEFIT_POLICY: '未知福利政策',
}

function getIssueCodeLabel(code: string): string {
  return issueCodeLabels[code] || code
}

// 筛选后的问题
const filteredIssues = computed(() => {
  let list = props.issues

  if (severityFilter.value !== 'ALL') {
    list = list.filter(i => i.severity === severityFilter.value)
  }
  if (statusFilter.value === 'PENDING') {
    list = list.filter(i => i.resolution_status === 'PENDING')
  } else if (statusFilter.value !== 'ALL') {
    list = list.filter(i => i.resolution_status === statusFilter.value)
  }
  if (issueCodeFilter.value !== 'ALL') {
    list = list.filter(i => i.issue_code === issueCodeFilter.value)
  }
  if (searchText.value.trim()) {
    const q = searchText.value.trim().toLowerCase()
    list = list.filter(i =>
      (i.employee_name && i.employee_name.toLowerCase().includes(q)) ||
      (i.title && i.title.toLowerCase().includes(q)) ||
      (i.message && i.message.toLowerCase().includes(q))
    )
  }
  return list
})

// 仅未处理的筛选后问题
const filteredPendingIssues = computed(() => filteredIssues.value.filter(i => i.resolution_status === 'PENDING'))
const filteredPendingIds = computed(() => filteredPendingIssues.value.map(i => i.id))

// 全选/取消
const selectAll = ref(false)
const selectedIssueIds = ref<Set<number>>(new Set())

watch(selectAll, (val) => {
  if (val) {
    selectedIssueIds.value = new Set(filteredPendingIds.value)
  } else {
    selectedIssueIds.value = new Set()
  }
})

function toggleSelect(issueId: number) {
  const s = new Set(selectedIssueIds.value)
  if (s.has(issueId)) s.delete(issueId)
  else s.add(issueId)
  selectedIssueIds.value = s
  selectAll.value = filteredPendingIds.value.length > 0 &&
    filteredPendingIds.value.every(id => s.has(id))
}

function selectAllFiltered() {
  selectAll.value = true
  selectedIssueIds.value = new Set(filteredPendingIds.value)
}

function clearSelection() {
  selectAll.value = false
  selectedIssueIds.value = new Set()
}

// ===================== 问题分组 =====================
interface IssueGroup {
  issueCode: string
  title: string
  issues: IssueItem[]
  autoFixableCount: number
  manualCount: number
}

/** 独立管理折叠状态，不受 computed 重新计算影响 */
const expandedGroupCodes = ref<Set<string>>(new Set())

const groups = computed<IssueGroup[]>(() => {
  const map = new Map<string, IssueGroup>()
  for (const issue of filteredIssues.value) {
    const code = issue.issue_code
    if (!map.has(code)) {
      map.set(code, {
        issueCode: code,
        title: issue.title,
        issues: [],
        autoFixableCount: 0,
        manualCount: 0,
      })
    }
    const group = map.get(code)!
    group.issues.push(issue)
    if (issue.auto_fixable) group.autoFixableCount++
    else group.manualCount++
  }
  const result = Array.from(map.values())
  // 首次加载时默认展开第一组
  if (expandedGroupCodes.value.size === 0 && result.length > 0) {
    expandedGroupCodes.value = new Set([result[0].issueCode])
  }
  return result
})

function isGroupExpanded(code: string): boolean {
  return expandedGroupCodes.value.has(code)
}

function toggleGroup(code: string) {
  const s = new Set(expandedGroupCodes.value)
  if (s.has(code)) s.delete(code)
  else s.add(code)
  expandedGroupCodes.value = s
}

// ===================== 可批量操作的问题 =====================
const selectedAutoFixable = computed(() => {
  return props.issues.filter(i => selectedIssueIds.value.has(i.id) && i.auto_fixable && i.resolution_status === 'PENDING')
})
const selectedManualOnly = computed(() => {
  return props.issues.filter(i => selectedIssueIds.value.has(i.id) && !i.auto_fixable && i.resolution_status === 'PENDING')
})
const hasSelectedBlockers = computed(() => {
  return props.issues.some(i => selectedIssueIds.value.has(i.id) && i.severity === 'BLOCKER' && i.resolution_status === 'PENDING')
})

// ===================== 批量处理 =====================
const showBatchDialog = ref(false)
const batchAction = ref<'APPLY_RECOMMENDATION' | 'IGNORE'>('APPLY_RECOMMENDATION')
const showBatchPreview = ref(false)

function handleBatchResolve() {
  batchAction.value = 'APPLY_RECOMMENDATION'
  showBatchPreview.value = true
}

function handleBatchIgnore() {
  batchAction.value = 'IGNORE'
  // 批量忽略直接触发，不弹预览
  const ids = Array.from(selectedIssueIds.value)
  if (ids.length === 0) return
  emit('batch-resolve', ids, 'IGNORE')
  clearSelection()
}

function confirmBatchResolve() {
  showBatchPreview.value = false
  const ids = Array.from(selectedAutoFixable.value.map(i => i.id))
  if (ids.length === 0) return
  emit('batch-resolve', ids, 'APPLY_RECOMMENDATION')
  clearSelection()
}

// ===================== 单条操作 =====================
const editingIssue = ref<IssueItem | null>(null)
const showDrawer = ref(false)

function handleAction(issue: IssueItem, action: string) {
  if (action === 'MODIFY_VALUE') {
    editingIssue.value = issue
    showDrawer.value = true
  } else {
    emit('resolve', issue, action)
  }
}

function handleModifySubmit(issue: IssueItem, value: string, note: string) {
  emit('modify-submit', issue, value, note)
  showDrawer.value = false
  editingIssue.value = null
}

// ===================== 统计 =====================
const stats = computed(() => {
  const total = props.issues.length
  const blockers = props.issues.filter(i => i.severity === 'BLOCKER' && i.resolution_status === 'PENDING').length
  const warnings = props.issues.filter(i => i.severity === 'WARNING' && i.resolution_status === 'PENDING').length
  const resolved = props.issues.filter(i => i.resolution_status !== 'PENDING').length
  return { total, blockers, warnings, resolved }
})

// 严重程度标签
function severityBadge(severity: string) {
  if (severity === 'BLOCKER') return { label: '阻断', color: '#E11D48', background: '#FFF1F2' }
  if (severity === 'WARNING') return { label: '提醒', color: '#D97706', background: '#FFF7E8' }
  return { label: '提示', color: '#6366F1', background: '#EEF2FF' }
}

function statusLabel(status: string) {
  if (status === 'PENDING') return '未处理'
  if (status === 'RESOLVED') return '已解决'
  if (status === 'IGNORED') return '已忽略'
  if (status === 'DEFERRED') return '已推迟'
  return status
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    ACCEPT: '接受',
    MODIFY_VALUE: '修改',
    MAP_VALUE: '映射',
    SELECT_EMPLOYEE: '选择员工',
    CREATE_NEW_EMPLOYEE: '新建员工',
    CONFIRM_REEMPLOYMENT: '确认重新入职',
    SKIP_ROW: '跳过',
    IGNORE: '忽略',
    DEFER: '稍后处理',
    USE_SYSTEM_CALCULATION: '采纳系统计算',
    USE_NORMALIZED_VALUE: '采纳标准值',
    IGNORE_SOURCE_VALUE: '忽略Excel值',
  }
  return map[action] || action
}

function isExpandable(issue: IssueItem): boolean {
  return !!(issue.message && issue.message.length > 60)
}

const expandedMessages = ref<Set<number>>(new Set())

function toggleMessage(issueId: number) {
  const s = new Set(expandedMessages.value)
  if (s.has(issueId)) s.delete(issueId)
  else s.add(issueId)
}
</script>

<template>
  <div class="issue-step">
    <!-- ==================== 顶部统计操作栏 ==================== -->
    <div class="toolbar">
      <div class="toolbar-stats">
        <span class="stat total">全部问题：{{ stats.total }}</span>
        <span class="stat blocker">阻断：{{ stats.blockers }}</span>
        <span class="stat warning">提醒：{{ stats.warnings }}</span>
        <span class="stat resolved">已处理：{{ stats.resolved }}</span>
      </div>
      <div class="toolbar-filters">
        <select v-model="issueCodeFilter" class="filter-select">
          <option value="ALL">全部类型</option>
          <option v-for="code in issueCodeOptions" :key="code" :value="code">{{ getIssueCodeLabel(code) }}</option>
        </select>
        <select v-model="severityFilter" class="filter-select">
          <option value="ALL">全部级别</option>
          <option value="BLOCKER">阻断</option>
          <option value="WARNING">提醒</option>
        </select>
        <select v-model="statusFilter" class="filter-select">
          <option value="ALL">全部状态</option>
          <option value="PENDING">未处理</option>
          <option value="RESOLVED">已解决</option>
          <option value="IGNORED">已忽略</option>
        </select>
        <div class="search-box">
          <Search :size="14" />
          <input v-model="searchText" type="text" placeholder="搜索员工/问题..." class="search-input" />
          <X v-if="searchText" :size="14" class="search-clear" @click="searchText = ''" />
        </div>
      </div>
      <div class="toolbar-actions">
        <BaseButton size="sm" variant="ghost" :disabled="filteredPendingIds.length === 0"
          @click="selectAllFiltered">
          {{ selectAll ? '取消全选' : `全选当前（${filteredPendingIds.length}）` }}
        </BaseButton>
        <BaseButton size="sm" variant="primary"
          :disabled="selectedAutoFixable.length === 0 || hasSelectedBlockers"
          title="对选中的可自动处理问题应用推荐处理"
          @click="handleBatchResolve">
          批量按推荐处理 ({{ selectedAutoFixable.length }})
        </BaseButton>
        <BaseButton size="sm" variant="secondary"
          :disabled="selectedIssueIds.size === 0 || hasSelectedBlockers"
          title="批量忽略选中的提醒问题"
          @click="handleBatchIgnore">
          批量忽略 ({{ selectedIssueIds.size }})
        </BaseButton>
        <BaseButton size="sm" variant="ghost" :disabled="selectedIssueIds.size === 0"
          @click="clearSelection">
          清除选择
        </BaseButton>
      </div>
    </div>

    <!-- ==================== 问题列表 ==================== -->
    <div class="issue-list">
      <div v-if="loading" class="loading-state">加载中...</div>

      <div v-else-if="filteredIssues.length === 0 && props.issues.length > 0" class="empty-filter">
        <BaseEmpty title="无匹配问题" description="当前筛选条件下没有问题，请调整筛选条件" />
      </div>

      <div v-else-if="props.issues.length === 0">
        <BaseEmpty title="没有问题" description="所有数据正常" />
      </div>

      <!-- 分组展示 -->
      <div v-else v-for="group in groups" :key="group.issueCode" class="issue-group">
        <div class="group-header" @click="toggleGroup(group.issueCode)">
          <span class="group-toggle">
            <ChevronDown v-if="isGroupExpanded(group.issueCode)" :size="14" />
            <ChevronRight v-else :size="14" />
          </span>
          <span class="group-title">{{ group.title }}</span>
          <span class="group-count">{{ group.issues.length }}</span>
          <span v-if="group.autoFixableCount > 0" class="group-tag auto">可自动处理 {{ group.autoFixableCount }}</span>
          <span v-if="group.manualCount > 0" class="group-tag manual">需人工 {{ group.manualCount }}</span>
        </div>

        <div v-if="isGroupExpanded(group.issueCode)" class="group-table-wrap">
          <table class="issue-table">
            <thead>
              <tr>
                <th class="col-check">
                  <input type="checkbox" :checked="group.issues.every(i => i.resolution_status !== 'PENDING' || selectedIssueIds.has(i.id))"
                    :indeterminate="group.issues.some(i => i.resolution_status === 'PENDING' && selectedIssueIds.has(i.id)) && !group.issues.every(i => i.resolution_status !== 'PENDING' || selectedIssueIds.has(i.id))"
                    @change="group.issues.filter(i => i.resolution_status === 'PENDING').forEach(i => toggleSelect(i.id))" />
                </th>
                <th class="col-employee">员工</th>
                <th class="col-issue">问题</th>
                <th class="col-source">Excel数据</th>
                <th class="col-system">系统结果</th>
                <th class="col-recommend">推荐</th>
                <th class="col-status">状态</th>
                <th class="col-action">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="issue in group.issues" :key="issue.id"
                :class="['issue-row', `row-${issue.severity.toLowerCase()}`, {
                  'row-resolved': issue.resolution_status !== 'PENDING',
                  'row-selected': selectedIssueIds.has(issue.id)
                }]"
              >
                <!-- 选择框 -->
                <td class="col-check">
                  <input type="checkbox" :checked="selectedIssueIds.has(issue.id)"
                    :disabled="issue.resolution_status !== 'PENDING'"
                    @change="toggleSelect(issue.id)" />
                </td>

                <!-- 员工 -->
                <td class="col-employee">
                  <div class="employee-cell">
                    <span class="emp-name">{{ issue.employee_name || '—' }}</span>
                    <span v-if="issue.row_no" class="row-no">#{{ issue.row_no }}</span>
                  </div>
                </td>

                <!-- 问题 -->
                <td class="col-issue">
                  <div class="issue-cell">
                    <div class="issue-title-row">
                      <BaseBadge v-bind="severityBadge(issue.severity)" size="sm" />
                      <span class="issue-title" :title="issue.title">{{ issue.title }}</span>
                    </div>
                    <div v-if="issue.message" class="issue-message" :class="{ expanded: expandedMessages.has(issue.id) }"
                      @click="isExpandable(issue) && toggleMessage(issue.id)">
                      {{ issue.message }}
                      <span v-if="isExpandable(issue) && !expandedMessages.has(issue.id)" class="expand-hint">展开</span>
                    </div>
                  </div>
                </td>

                <!-- Excel数据 -->
                <td class="col-source">
                  <span class="cell-value mono" :title="String(issue.source_value ?? issue.old_value ?? '')">
                    {{ issue.source_value ?? issue.old_value ?? '—' }}
                  </span>
                </td>

                <!-- 系统结果 -->
                <td class="col-system">
                  <span class="cell-value mono" :title="String(issue.system_value ?? issue.new_value ?? '')">
                    {{ issue.system_value ?? issue.new_value ?? '—' }}
                  </span>
                </td>

                <!-- 推荐处理 -->
                <td class="col-recommend">
                  <span class="recommend-text" :title="issue.recommendation_text || ''">
                    {{ issue.recommendation_text || '—' }}
                  </span>
                </td>

                <!-- 状态 -->
                <td class="col-status">
                  <span :class="['status-badge', issue.resolution_status.toLowerCase()]">
                    {{ statusLabel(issue.resolution_status) }}
                  </span>
                </td>

                <!-- 操作 -->
                <td class="col-action">
                  <div class="action-btns">
                    <template v-if="issue.resolution_status === 'PENDING'">
                      <button v-if="issue.allowed_actions.includes('MODIFY_VALUE')"
                        class="action-btn edit" @click="handleAction(issue, 'MODIFY_VALUE')">修改</button>
                      <button v-if="issue.auto_fixable"
                        class="action-btn auto" @click="handleAction(issue, 'USE_SYSTEM_CALCULATION')">采纳推荐</button>
                      <button v-if="issue.allowed_actions.includes('IGNORE')"
                        class="action-btn ignore" @click="handleAction(issue, 'IGNORE')">忽略</button>
                      <button v-for="action in issue.allowed_actions.filter(a => !['MODIFY_VALUE','IGNORE','ACCEPT'].includes(a))"
                        :key="action" class="action-btn"
                        @click="handleAction(issue, action)">{{ actionLabel(action) }}</button>
                      <button v-if="issue.allowed_actions.includes('ACCEPT')"
                        class="action-btn accept" @click="handleAction(issue, 'ACCEPT')">接受</button>
                    </template>
                    <span v-else class="resolved-note">{{ issue.resolution_action ? actionLabel(issue.resolution_action) : '' }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ==================== 底部操作 ==================== -->
    <div class="form-actions">
      <BaseButton variant="ghost" @click="emit('prev')">上一步</BaseButton>
      <BaseButton variant="primary" :disabled="!allBlockersResolved" @click="emit('continue')">
        继续 <ChevronRight :size="16" />
      </BaseButton>
    </div>

    <!-- ==================== 编辑抽屉 ==================== -->
    <RosterIssueEditDrawer
      :show="showDrawer"
      :issue="editingIssue"
      @modify-submit="handleModifySubmit"
      @close="showDrawer = false; editingIssue = null"
    />

    <!-- ==================== 批量处理预览对话框 ==================== -->
    <RosterBatchResolveDialog
      :show="showBatchPreview"
      :issues="props.issues.filter(i => selectedAutoFixable.map(s => s.id).includes(i.id))"
      :loading="false"
      @confirm="confirmBatchResolve"
      @cancel="showBatchPreview = false"
    />
  </div>
</template>

<style scoped>
.issue-step { display: flex; flex-direction: column; gap: 16px; }

/* ==================== 顶部操作栏（滚动时固定） ==================== */
.toolbar { position: sticky; top: 0; z-index: 10; background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: 0 1px 4px rgba(0,0,0,0.08); padding: 14px 20px; display: flex; flex-direction: column; gap: 10px; }
.toolbar-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.stat { font-size: var(--font-size-sm); font-weight: 500; }
.stat.total { color: var(--color-text-primary); }
.stat.blocker { color: var(--color-danger); }
.stat.warning { color: var(--color-warning); }
.stat.resolved { color: var(--color-success); }
.toolbar-filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.filter-select { padding: 4px 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-xs); background: var(--color-bg); color: var(--color-text-primary); }
.search-box { display: flex; align-items: center; gap: 4px; padding: 4px 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); flex: 1; min-width: 160px; color: var(--color-text-secondary); }
.search-input { border: none; background: none; outline: none; font-size: var(--font-size-xs); flex: 1; color: var(--color-text-primary); }
.search-clear { cursor: pointer; }
.toolbar-actions { display: flex; gap: 6px; flex-wrap: wrap; }

/* ==================== 问题列表 ==================== */
.issue-list { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); overflow: hidden; }
.loading-state { padding: 40px; text-align: center; color: var(--color-text-secondary); }
.empty-filter { padding: 24px; }

/* ==================== 分组 ==================== */
.issue-group { border-bottom: 1px solid var(--color-border); }
.issue-group:last-child { border-bottom: none; }
.group-header { display: flex; align-items: center; gap: 8px; padding: 10px 16px; cursor: pointer; user-select: none; background: var(--color-bg); }
.group-header:hover { background: var(--color-surface); }
.group-toggle { color: var(--color-text-tertiary); display: flex; }
.group-title { font-size: var(--font-size-sm); font-weight: 600; flex: 1; }
.group-count { font-size: var(--font-size-xs); color: var(--color-text-secondary); min-width: 28px; text-align: right; }
.group-tag { font-size: var(--font-size-xs); padding: 1px 8px; border-radius: 10px; font-weight: 500; }
.group-tag.auto { background: #ECFDF5; color: #059669; }
.group-tag.manual { background: #FFF7E8; color: #D97706; }

/* ==================== 紧凑表格 ==================== */
.group-table-wrap { overflow-x: auto; }
.issue-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-xs); }
.issue-table thead { background: var(--color-bg); }
.issue-table th { padding: 8px 12px; text-align: left; font-weight: 600; color: var(--color-text-secondary); white-space: nowrap; border-bottom: 1px solid var(--color-border); }
.issue-table td { padding: 6px 12px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.issue-table tbody tr { height: 48px; transition: background 0.1s; }
.issue-table tbody tr:hover { background: var(--color-bg); }
.issue-table tbody tr.row-resolved { opacity: 0.55; }
.issue-table tbody tr.row-selected { background: #EEF2FF; }
.issue-table tbody tr.row-blocker { border-left: 3px solid var(--color-danger); }
.issue-table tbody tr.row-warning { border-left: 3px solid var(--color-warning); }

/* 列宽 */
.col-check { width: 36px; text-align: center; }
.col-check input { cursor: pointer; }
.col-employee { min-width: 100px; }
.col-issue { min-width: 180px; }
.col-source { min-width: 100px; max-width: 160px; }
.col-system { min-width: 100px; max-width: 160px; }
.col-recommend { min-width: 140px; max-width: 200px; }
.col-status { width: 72px; }
.col-action { min-width: 140px; }

/* 单元格内容 */
.employee-cell { display: flex; flex-direction: column; gap: 1px; }
.emp-name { font-weight: 500; color: var(--color-text-primary); }
.row-no { font-size: 10px; color: var(--color-text-tertiary); }
.issue-cell { display: flex; flex-direction: column; gap: 2px; }
.issue-title-row { display: flex; align-items: center; gap: 6px; }
.issue-title { font-weight: 500; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.issue-message { font-size: 10px; color: var(--color-text-tertiary); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; cursor: default; }
.issue-message.expanded { -webkit-line-clamp: unset; }
.expand-hint { color: var(--color-primary); cursor: pointer; margin-left: 4px; }
.cell-value { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
.cell-value.mono { font-family: monospace; font-size: 10px; color: var(--color-text-secondary); }
.recommend-text { font-size: 10px; color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.3; }

/* 状态 */
.status-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 500; white-space: nowrap; }
.status-badge.pending { background: #F3F4F6; color: #6B7280; }
.status-badge.resolved { background: #ECFDF5; color: #059669; }
.status-badge.ignored { background: #FFF7E8; color: #D97706; }
.status-badge.deferred { background: #EEF2FF; color: #4F46E5; }

/* 操作按钮 */
.action-btns { display: flex; gap: 4px; flex-wrap: wrap; }
.action-btn { padding: 2px 8px; border-radius: var(--radius-sm); font-size: 10px; font-weight: 500; cursor: pointer; border: 1px solid var(--color-border); background: var(--color-surface); color: var(--color-text-primary); white-space: nowrap; }
.action-btn:hover { background: var(--color-bg); }
.action-btn.edit { color: var(--color-primary); border-color: var(--color-primary-soft); }
.action-btn.auto { color: #059669; border-color: #A7F3D0; background: #ECFDF5; }
.action-btn.ignore { color: var(--color-text-tertiary); border-color: transparent; }
.action-btn.accept { color: var(--color-primary); border-color: var(--color-primary-soft); }
.action-btn.primary { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.resolved-note { font-size: 10px; color: var(--color-text-tertiary); }

/* 底部 */
.form-actions { display: flex; justify-content: flex-end; gap: 8px; background: var(--color-surface); border-radius: var(--radius-lg); padding: 16px 20px; box-shadow: var(--shadow-card); }
</style>
