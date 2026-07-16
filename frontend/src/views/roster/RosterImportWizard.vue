<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Upload,
  FileText,
  Check,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronRight,
  ChevronLeft,
  Eye,
  Download,
  List,
  Hash,
  X,
  HelpCircle,
  ArrowRight,
  Loader2,
} from 'lucide-vue-next'
import { formatDateTime } from '@/utils/date'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { getStatusLabel } from '@/constants/status'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseBadge from '@/components/base/BaseBadge.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseEmpty from '@/components/base/BaseEmpty.vue'
import {
  uploadRoster,
  saveMapping,
  generatePreview,
  getBatchIssues,
  resolveIssue,
  commitImport,
  getFileDownloadUrl,
  getFieldDefinitions,
  getBatchDetail,
} from '@/services/rosterImportService'
import type {
  RosterUploadResponse,
  ColumnMapping,
  FieldDefinition,
  PreviewResponse,
  RowPreviewItem,
  IssueItem,
  PreviewSummary,
  CommitConfirmation,
  CommitResponse,
} from '@/types/roster-import'

const router = useRouter()
const route = useRoute()
const { showToast } = useToast()
const { show: showConfirm, loading: confirmLoading, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

// ===================== Wizard State =====================
const currentStep = ref(1)
const wizardLoading = ref(false)
const pageLoading = ref(true)

const steps = [
  { num: 1, title: '上传文件' },
  { num: 2, title: '字段映射' },
  { num: 3, title: '数据预览' },
  { num: 4, title: '处理问题' },
  { num: 5, title: '确认导入' },
  { num: 6, title: '导入结果' },
]

// ===================== Step 1: Upload =====================
const selectedFile = ref<File | null>(null)
const uploadMode = ref<'INITIALIZE' | 'SYNC'>('SYNC')
const sheetNames = ref<string[]>([])
const selectedSheet = ref('')
const uploadResult = ref<RosterUploadResponse | null>(null)
const isDuplicate = ref(false)
const existingBatchId = ref<number | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const modeOptions = [
  { label: '后续同步（SYNC）', value: 'SYNC' },
  { label: '首次初始化（INITIALIZE）', value: 'INITIALIZE' },
]

const modeDescriptions: Record<string, string> = {
  SYNC: '更新已有员工信息，新增员工入职，自动更新允许的字段',
  INITIALIZE: '首次将花名册整体导入系统，建立初始档案和任职记录',
}

async function handleFileChange() {
  if (!fileInputRef.value?.files?.length) return
  selectedFile.value = fileInputRef.value.files[0]
  uploadResult.value = null
  sheetNames.value = []
  selectedSheet.value = ''
  isDuplicate.value = false
  existingBatchId.value = null
  resetBatchState()
}

function onDropzoneClick() {
  fileInputRef.value?.click()
}

async function handleUpload() {
  if (!selectedFile.value) {
    showToast({ message: '请选择文件', type: 'warning' })
    return
  }

  wizardLoading.value = true
  try {
    const result = await uploadRoster(
      selectedFile.value,
      uploadMode.value,
      selectedSheet.value || undefined,
    )
    resetBatchState()
    uploadResult.value = result
    sheetNames.value = result.sheet_names
    if (result.selected_sheet && !selectedSheet.value) {
      selectedSheet.value = result.selected_sheet
    }

    // Check if file was already imported
    if (result.suggestion?.includes('already') || result.suggestion?.includes('重复')) {
      isDuplicate.value = true
    }

    showToast({ message: '文件上传成功', type: 'success' })
    currentStep.value = 2
  } catch (e: any) {
    showToast({ message: e.message || '上传失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

// ===================== Step 2: Field Mapping =====================
const columnMappings = ref<ColumnMapping[]>([])
const fieldDefinitions = ref<FieldDefinition[]>([])
const mappingBatchId = ref<number | null>(null)

const fieldDefOptions = computed(() => {
  return [
    { label: '仅保留原始数据（不映射）', value: '' },
    ...fieldDefinitions.value.map(fd => ({
      label: `${fd.label}${fd.required ? ' *' : ''}`,
      value: fd.key,
    })),
  ]
})

const unmappedRequiredFields = computed(() => {
  const requiredKeys = fieldDefinitions.value.filter(fd => fd.required).map(fd => fd.key)
  const mappedKeys = columnMappings.value
    .filter(cm => cm.is_mapped && cm.target_field_key)
    .map(cm => cm.target_field_key)
  return requiredKeys.filter(key => !mappedKeys.includes(key))
})

async function loadMapping() {
  if (!uploadResult.value) return
  wizardLoading.value = true
  try {
    const detail = await getBatchDetail(uploadResult.value.batch_id)
    const defs = await getFieldDefinitions()
    fieldDefinitions.value = defs
    columnMappings.value = normalizeColumnMappings(detail, defs)
    mappingBatchId.value = uploadResult.value.batch_id
  } catch (e: any) {
    showToast({ message: e.message || '加载映射失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

function normalizeColumnMappings(detail: Record<string, unknown>, defs: FieldDefinition[]): ColumnMapping[] {
  const raw = detail.column_mappings || detail.mappings || detail.current_mappings || detail.header_row || []
  const requiredKeys = new Set(defs.filter(fd => fd.required).map(fd => fd.key))

  if (Array.isArray(raw)) {
    return raw
      .map((item: any) => {
        const sourceHeader = item.source_header || item.header
        if (!sourceHeader) return null
        const targetField = item.target_field_key ?? item.field_key ?? null
        return {
          source_header: String(sourceHeader),
          source_header_normalized: String(item.source_header_normalized || sourceHeader).trim().toLowerCase(),
          target_field_key: targetField,
          is_mapped: !!targetField,
          is_required: !!targetField && requiredKeys.has(targetField),
          is_unknown: !targetField,
          save_as_alias: !!item.save_as_alias,
        } as ColumnMapping
      })
      .filter(Boolean) as ColumnMapping[]
  }

  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, unknown>).map(([header, fieldKey]) => ({
      source_header: header,
      source_header_normalized: header.trim().toLowerCase(),
      target_field_key: fieldKey ? String(fieldKey) : null,
      is_mapped: !!fieldKey,
      is_required: !!fieldKey && requiredKeys.has(String(fieldKey)),
      is_unknown: !fieldKey,
      save_as_alias: false,
    }))
  }

  return []
}

function updateMapping(header: string, fieldKey: string) {
  const mapping = columnMappings.value.find(m => m.source_header === header)
  if (mapping) {
    mapping.target_field_key = fieldKey || null
    mapping.is_mapped = !!fieldKey
  }
}

async function handleSaveMapping() {
  if (!uploadResult.value) return
  if (unmappedRequiredFields.value.length > 0) {
    showToast({
      message: `必填字段尚未映射：${unmappedRequiredFields.value.join(', ')}`,
      type: 'warning',
    })
    return
  }

  wizardLoading.value = true
  try {
    const mappings: Record<string, string | null> = {}
    columnMappings.value.forEach(m => {
      mappings[m.source_header] = m.target_field_key
    })
    await saveMapping(uploadResult.value.batch_id, { mappings })
    showToast({ message: '映射保存成功', type: 'success' })
    currentStep.value = 3
  } catch (e: any) {
    showToast({ message: e.message || '保存映射失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

// ===================== Step 3: Preview =====================
const previewData = ref<PreviewResponse | null>(null)
const previewRows = ref<RowPreviewItem[]>([])
const previewFilter = ref('ALL')

const filterTabs = [
  { label: '全部', value: 'ALL' },
  { label: '新增', value: 'NEW' },
  { label: '更新', value: 'UPDATE' },
  { label: '待确认', value: 'NEEDS_CONFIRMATION' },
  { label: '错误', value: 'ERROR' },
  { label: '无变化', value: 'UNCHANGED' },
  { label: '跳过', value: 'SKIPPED' },
]

const filteredRows = computed(() => {
  if (previewFilter.value === 'ALL') return previewRows.value
  return previewRows.value.filter(r => r.row_status === previewFilter.value)
})

function resetBatchState() {
  columnMappings.value = []
  fieldDefinitions.value = []
  mappingBatchId.value = null
  previewData.value = null
  previewRows.value = []
  previewFilter.value = 'ALL'
  issues.value = []
}

const previewSummaryList = computed(() => {
  if (!previewData.value) return []
  const s = previewData.value.summary
  return [
    { label: '新增员工', count: s.new_count, color: '#16825D', bg: '#EAF8F1' },
    { label: '自动更新', count: s.update_count, color: '#2563EB', bg: '#EFF6FF' },
    { label: '需要确认', count: s.confirmation_count, color: '#D97706', bg: '#FFF7E8' },
    { label: '数据错误', count: s.error_count, color: '#E11D48', bg: '#FFF1F2' },
    { label: '无变化', count: s.unchanged_count, color: '#667085', bg: '#F2F4F7' },
    { label: '跳过', count: s.skipped_count, color: '#98A2B3', bg: '#F2F4F7' },
  ]
})

const expandedRowNos = ref<Set<number>>(new Set())

function toggleRowExpand(rowNo: number) {
  const newSet = new Set(expandedRowNos.value)
  if (newSet.has(rowNo)) {
    newSet.delete(rowNo)
  } else {
    newSet.add(rowNo)
  }
  expandedRowNos.value = newSet
}

const rowStatusInfo: Record<string, { label: string; color: string; background: string }> = {
  NEW: { label: '新增', color: '#16825D', background: '#EAF8F1' },
  UPDATE: { label: '更新', color: '#2563EB', background: '#EFF6FF' },
  UNCHANGED: { label: '无变化', color: '#667085', background: '#F2F4F7' },
  NEEDS_CONFIRMATION: { label: '待确认', color: '#D97706', background: '#FFF7E8' },
  ERROR: { label: '错误', color: '#E11D48', background: '#FFF1F2' },
  SKIPPED: { label: '跳过', color: '#98A2B3', background: '#F2F4F7' },
  IMPORTED: { label: '已导入', color: '#16825D', background: '#EAF8F1' },
}

const changeTypeLabel: Record<string, string> = {
  NEW: '新增',
  UPDATE: '更新',
  UNCHANGED: '无变化',
  CONFIRMATION: '需确认',
  REMOVAL: '移除',
}

async function loadPreview() {
  if (!uploadResult.value) return
  wizardLoading.value = true
  try {
    const data = await generatePreview(uploadResult.value.batch_id)
    previewData.value = data
    previewRows.value = data.rows || []
    // Check for issues
    if (data.summary.blocker_count > 0 || data.summary.warning_count > 0) {
      currentStep.value = 4
    } else {
      currentStep.value = 5
    }
    showToast({ message: '预览生成成功', type: 'success' })
  } catch (e: any) {
    showToast({ message: e.message || '生成预览失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

function continueAfterPreview() {
  if (previewData.value && (previewData.value.summary.blocker_count > 0 || previewData.value.summary.warning_count > 0)) {
    currentStep.value = 4
  } else {
    currentStep.value = 5
  }
}

// ===================== Step 4: Issues =====================
const issues = ref<IssueItem[]>([])
const blockerIssues = computed(() => issues.value.filter(i => i.severity === 'BLOCKER' && i.resolution_status === 'PENDING'))
const warningIssues = computed(() => issues.value.filter(i => i.severity === 'WARNING' && i.resolution_status === 'PENDING'))
const resolvedIssues = computed(() => issues.value.filter(i => i.resolution_status !== 'PENDING'))
const allBlockersResolved = computed(() => issues.value.filter(i => i.severity === 'BLOCKER').every(i => i.resolution_status !== 'PENDING'))

// Issue action state
const editingIssueId = ref<number | null>(null)
const issueEditValue = ref('')
const issueEditNote = ref('')

async function loadIssues() {
  if (!uploadResult.value) return
  wizardLoading.value = true
  try {
    const data = await getBatchIssues(uploadResult.value.batch_id)
    issues.value = data.items || []
  } catch (e: any) {
    showToast({ message: e.message || '加载问题失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

async function handleIssueAction(issue: IssueItem, action: string) {
  if (action === 'modify') {
    editingIssueId.value = issue.id
    issueEditValue.value = String(issue.new_value ?? '')
    issueEditNote.value = ''
    return
  }

  wizardLoading.value = true
  try {
    const payload: { action: string; value?: unknown; note?: string } = { action }
    if (action === 'accept' && issue.new_value !== undefined) {
      payload.value = issue.new_value
    }
    await resolveIssue(uploadResult.value!.batch_id, issue.id, payload)
    showToast({ message: '问题已处理', type: 'success' })
    await loadIssues()
  } catch (e: any) {
    showToast({ message: e.message || '处理失败', type: 'error' })
  } finally {
    wizardLoading.value = false
    editingIssueId.value = null
  }
}

async function handleIssueModifySubmit(issue: IssueItem) {
  if (!issueEditValue.value.trim()) {
    showToast({ message: '请输入修改值', type: 'warning' })
    return
  }
  wizardLoading.value = true
  try {
    await resolveIssue(uploadResult.value!.batch_id, issue.id, {
      action: 'modify',
      value: issueEditValue.value,
      note: issueEditNote.value || undefined,
    })
    showToast({ message: '修改已保存', type: 'success' })
    await loadIssues()
  } catch (e: any) {
    showToast({ message: e.message || '修改失败', type: 'error' })
  } finally {
    wizardLoading.value = false
    editingIssueId.value = null
  }
}

function cancelIssueEdit() {
  editingIssueId.value = null
  issueEditValue.value = ''
  issueEditNote.value = ''
}

const actionButtonInfo: Record<string, { label: string; variant: string }> = {
  accept: { label: '接受建议', variant: 'primary' },
  modify: { label: '修改', variant: 'secondary' },
  map: { label: '映射', variant: 'secondary' },
  create: { label: '新建', variant: 'primary' },
  skip: { label: '跳过此员工', variant: 'danger' },
  ignore: { label: '忽略', variant: 'ghost' },
}

function canContinueFromIssues() {
  return allBlockersResolved.value
}

function goToStep5() {
  if (!canContinueFromIssues()) {
    showToast({ message: '请先处理所有阻断问题', type: 'warning' })
    return
  }
  currentStep.value = 5
}

// ===================== Step 5: Confirm =====================
const commitConfirmation = ref<CommitConfirmation | null>(null)
const showSecondConfirm = ref(false)

const confirmationItems = computed(() => {
  if (!commitConfirmation.value) return []
  const c = commitConfirmation.value!
  return [
    { label: '新增员工', count: c.will_create, color: '#16825D' },
    { label: '更新员工', count: c.will_update, color: '#2563EB' },
    { label: '创建异动', count: c.will_create_changes, color: '#7C3AED' },
    { label: '创建薪酬记录', count: c.will_create_compensations, color: '#D97706' },
    { label: '创建备注', count: c.will_create_notes, color: '#0F9F94' },
    { label: '创建待确认事项', count: c.will_create_confirmations, color: '#E11D48' },
    { label: '跳过行', count: c.will_skip, color: '#98A2B3' },
  ].filter(item => item.count > 0)
})

function requestFirstConfirm() {
  if (!previewData.value) return
  const s = previewData.value.summary
  commitConfirmation.value = {
    will_create: s.new_count,
    will_update: s.update_count,
    will_create_changes: 0,
    will_create_compensations: 0,
    will_create_notes: 0,
    will_create_confirmations: s.confirmation_count,
    will_skip: s.skipped_count,
  }
  showSecondConfirm.value = true
}

function requestSecondConfirm() {
  showSecondConfirm.value = false
  confirm({
    title: '确认导入',
    message: '确认提交本次导入？此操作将写入业务数据，不可撤销。',
    confirmText: '确认导入',
    danger: true,
    onConfirm: async () => {
      await handleCommit()
    },
  })
}

// ===================== Step 6: Result =====================
const commitResult = ref<CommitResponse | null>(null)
const commitFailed = ref(false)
const commitErrorMessage = ref('')

async function handleCommit() {
  if (!uploadResult.value) return
  wizardLoading.value = true
  commitFailed.value = false
  commitErrorMessage.value = ''
  try {
    const result = await commitImport(uploadResult.value.batch_id)
    commitResult.value = result
    currentStep.value = 6
    showToast({ message: '导入成功', type: 'success' })
  } catch (e: any) {
    commitFailed.value = true
    commitErrorMessage.value = e.message || '导入执行失败，系统没有写入业务数据'
    currentStep.value = 6
    showToast({ message: '导入失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

const commitSummaryItems = computed(() => {
  if (!commitResult.value?.summary) return []
  const s = commitResult.value.summary
  return [
    { label: '新增员工', count: s.new_count, color: '#16825D' },
    { label: '自动更新', count: s.update_count, color: '#2563EB' },
    { label: '需要确认', count: s.confirmation_count, color: '#D97706' },
    { label: '数据错误', count: s.error_count, color: '#E11D48' },
    { label: '无变化', count: s.unchanged_count, color: '#667085' },
    { label: '跳过', count: s.skipped_count, color: '#98A2B3' },
  ].filter(item => item.count > 0)
})

function viewDetails() {
  if (uploadResult.value) {
    router.push(`/roster-imports/${uploadResult.value.batch_id}`)
  }
}

function downloadResultFile() {
  if (uploadResult.value) {
    const url = getFileDownloadUrl(uploadResult.value.batch_id)
    window.open(url, '_blank')
  }
}

function goBackToList() {
  // 如果是从员工中心跳转过来的，返回员工列表
  if (route.query.from === 'employees') {
    router.push('/employees')
  } else {
    router.push('/roster-imports')
  }
}

// ===================== Navigation =====================
function canGoNext(): boolean {
  switch (currentStep.value) {
    case 1: return !!uploadResult.value
    case 2: return unmappedRequiredFields.value.length === 0
    case 3: return true
    case 4: return canContinueFromIssues()
    case 5: return !!commitConfirmation.value
    default: return false
  }
}

function goNext() {
  if (currentStep.value === 1 && uploadResult.value) {
    currentStep.value = 2
  } else if (currentStep.value === 2) {
    handleSaveMapping()
  } else if (currentStep.value === 3) {
    continueAfterPreview()
  } else if (currentStep.value === 4) {
    goToStep5()
  }
}

function goPrev() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

// ===================== Init =====================
onMounted(() => {
  pageLoading.value = false
})

// Watch for step changes to load data
watch(currentStep, async (step) => {
  if (step === 2 && uploadResult.value && mappingBatchId.value !== uploadResult.value.batch_id) {
    await loadMapping()
  }
  if (step === 3 && !previewData.value) {
    await loadPreview()
  }
  if (step === 4 && issues.value.length === 0) {
    await loadIssues()
  }
})
</script>

<template>
  <div class="page">
    <!-- Page header -->
    <div class="page-header">
      <button class="back-link" @click="goBackToList">
        <ChevronLeft :size="16" />
        返回列表
      </button>
      <h1 class="page-title">花名册导入向导</h1>
    </div>

    <!-- Step indicator -->
    <div class="step-indicator">
      <div
        v-for="(step, idx) in steps"
        :key="step.num"
        class="step-item"
        :class="{
          'step-active': currentStep === step.num,
          'step-completed': currentStep > step.num,
        }"
      >
        <div class="step-circle">
          <Check v-if="currentStep > step.num" :size="14" />
          <span v-else>{{ step.num }}</span>
        </div>
        <span class="step-label">{{ step.title }}</span>
        <div v-if="idx < steps.length - 1" class="step-connector" :class="{ 'connector-active': currentStep > step.num }" />
      </div>
    </div>

    <!-- Loading overlay -->
    <div v-if="wizardLoading" class="loading-overlay">
      <Loader2 :size="32" class="spinner" />
      <span>处理中...</span>
    </div>

    <!-- ===================== Step 1: Upload ===================== -->
    <div v-show="currentStep === 1 && !wizardLoading" class="step-content">
      <div class="card step-card">
        <h2 class="step-title">上传花名册文件</h2>

        <!-- Mode selector -->
        <div class="form-section">
          <label class="form-label">导入模式</label>
          <div class="mode-options">
            <div
              v-for="modeOpt in modeOptions"
              :key="modeOpt.value"
              class="mode-card"
              :class="{ 'mode-selected': uploadMode === modeOpt.value }"
              @click="uploadMode = modeOpt.value as 'INITIALIZE' | 'SYNC'"
            >
              <div class="mode-radio" :class="{ 'radio-checked': uploadMode === modeOpt.value }">
                <div v-if="uploadMode === modeOpt.value" class="radio-dot" />
              </div>
              <div class="mode-info">
                <div class="mode-title">{{ modeOpt.label }}</div>
                <div class="mode-desc">{{ modeDescriptions[modeOpt.value] }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- File upload + Sheet selector row -->
        <div class="form-section">
          <label class="form-label">选择文件</label>
          <div
            class="dropzone"
            :class="{ 'has-file': !!selectedFile }"
            @click="onDropzoneClick"
            @dragover.prevent
            @drop.prevent
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".xlsx,.xlsm"
              class="file-input-hidden"
              @change="handleFileChange"
            />
            <template v-if="!selectedFile">
              <Upload :size="32" class="dropzone-icon" />
              <div class="dropzone-text">
                <span class="dropzone-primary">点击选择 Excel 文件</span>
                <span class="dropzone-hint">支持 .xlsx / .xlsm，最大 20MB</span>
              </div>
            </template>
            <template v-else>
              <FileText :size="24" class="dropzone-icon has-file-icon" />
              <div class="dropzone-text">
                <span class="dropzone-primary">{{ selectedFile.name }}</span>
                <span class="dropzone-hint">{{ (selectedFile.size / 1024).toFixed(1) }} KB</span>
              </div>
            </template>
          </div>
        </div>

        <!-- Sheet selector (shown when sheets detected) -->
        <div v-if="sheetNames.length > 0" class="form-section">
          <label class="form-label">工作表</label>
          <div class="sheet-list">
            <div
              v-for="sheet in sheetNames"
              :key="sheet"
              class="sheet-item"
              :class="{ 'sheet-selected': selectedSheet === sheet }"
              @click="selectedSheet = sheet"
            >
              <List :size="14" />
              <span>{{ sheet }}</span>
              <Check v-if="selectedSheet === sheet" :size="14" class="sheet-check" />
            </div>
          </div>
        </div>

        <!-- Duplicate warning -->
        <div v-if="isDuplicate" class="alert alert-warning">
          <AlertTriangle :size="16" />
          <span>该文件已导入过，继续操作将保持幂等，不会重复创建数据。</span>
        </div>

        <!-- Upload button -->
        <div class="form-actions">
          <BaseButton variant="ghost" @click="goBackToList">取消</BaseButton>
          <BaseButton
            variant="primary"
            :disabled="!selectedFile"
            :loading="wizardLoading"
            @click="handleUpload"
          >
            <Upload :size="16" />
            上传并继续
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Step 2: Field Mapping ===================== -->
    <div v-show="currentStep === 2 && !wizardLoading" class="step-content">
      <div class="card step-card">
        <h2 class="step-title">字段映射</h2>
        <p class="step-desc">确认 Excel 列与系统字段的对应关系。<span class="text-danger">*</span> 为必填字段。</p>

        <!-- Unmapped required warning -->
        <div v-if="unmappedRequiredFields.length > 0" class="alert alert-danger">
          <AlertCircle :size="16" />
          <span>以下必填字段尚未映射：{{ unmappedRequiredFields.join(', ') }}</span>
        </div>

        <div class="mapping-table-wrap">
          <table class="mapping-table">
            <thead>
              <tr>
                <th class="col-header">Excel 列名</th>
                <th class="col-arrow"></th>
                <th class="col-target">系统字段</th>
                <th class="col-status">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="mapping in columnMappings"
                :key="mapping.source_header"
                class="mapping-row"
              >
                <td class="col-header">
                  <span class="source-header">{{ mapping.source_header }}</span>
                </td>
                <td class="col-arrow">
                  <ArrowRight :size="14" />
                </td>
                <td class="col-target">
                  <select
                    :value="mapping.target_field_key || ''"
                    class="mapping-select"
                    @change="updateMapping(mapping.source_header, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="">— 不映射 —</option>
                    <optgroup v-for="group in [{ label: '系统字段', options: fieldDefinitions }]" :key="group.label" :label="group.label">
                      <option
                        v-for="fd in group.options"
                        :key="fd.key"
                        :value="fd.key"
                      >
                        {{ fd.label }}{{ fd.required ? ' *' : '' }}
                      </option>
                    </optgroup>
                  </select>
                </td>
                <td class="col-status">
                  <span v-if="mapping.is_mapped" class="status-mapped">
                    <Check :size="12" /> 已映射
                  </span>
                  <span v-else-if="mapping.target_field_key" class="status-mapped">
                    <Check :size="12" /> 已映射
                  </span>
                  <span v-else class="status-unmapped">
                    <AlertTriangle :size="12" /> 未映射
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="form-actions">
          <BaseButton variant="ghost" @click="goPrev">上一步</BaseButton>
          <BaseButton
            variant="primary"
            :disabled="unmappedRequiredFields.length > 0"
            :loading="wizardLoading"
            @click="handleSaveMapping"
          >
            <Check :size="16" />
            保存映射并继续
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Step 3: Preview ===================== -->
    <div v-show="currentStep === 3 && !wizardLoading" class="step-content">
      <div class="card step-card">
        <h2 class="step-title">数据预览</h2>
        <p class="step-desc">预览本次导入将执行的操作。</p>

        <!-- Summary cards -->
        <div v-if="previewSummaryList.length > 0" class="summary-cards">
          <div
            v-for="item in previewSummaryList"
            :key="item.label"
            class="summary-card"
            :style="{ borderTopColor: item.color }"
          >
            <div class="summary-count" :style="{ color: item.color }">{{ item.count }}</div>
            <div class="summary-label">{{ item.label }}</div>
          </div>
        </div>

        <!-- Filter tabs -->
        <div class="preview-filters">
          <button
            v-for="tab in filterTabs"
            :key="tab.value"
            class="filter-tab"
            :class="{ active: previewFilter === tab.value }"
            @click="previewFilter = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- Rows table -->
        <table class="preview-table">
          <thead>
            <tr>
              <th class="col-row">#</th>
              <th class="col-name">姓名</th>
              <th class="col-match">匹配员工</th>
              <th class="col-status-h">状态</th>
              <th class="col-changes">变化</th>
              <th class="col-actions-h"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredRows.length === 0">
              <td colspan="6" class="empty-cell">
                <BaseEmpty title="无匹配数据" />
              </td>
            </tr>
            <template v-for="row in filteredRows" :key="row.row_no">
              <tr class="preview-row" @click="toggleRowExpand(row.row_no)">
                <td class="col-row">{{ row.row_no }}</td>
                <td class="col-name">
                  <span class="row-name">{{ row.normalized_name }}</span>
                </td>
                <td class="col-match">
                  <span v-if="row.matched_employee_name" class="matched-name">
                    {{ row.matched_employee_name }}
                  </span>
                  <span v-else class="no-match">—</span>
                </td>
                <td class="col-status-h">
                  <BaseBadge
                    type="custom"
                    :label="rowStatusInfo[row.row_status]?.label || row.row_status"
                    :color="rowStatusInfo[row.row_status]?.color || '#98A2B3'"
                    :background="rowStatusInfo[row.row_status]?.background || '#F2F4F7'"
                    size="sm"
                  />
                </td>
                <td class="col-changes">
                  <span v-if="row.diff_fields && row.diff_fields.length > 0" class="change-count">
                    {{ row.diff_fields.length }} 项变化
                  </span>
                  <span v-else class="text-tertiary">—</span>
                </td>
                <td class="col-actions-h">
                  <ChevronRight
                    :size="14"
                    class="expand-icon"
                    :class="{ expanded: expandedRowNos.has(row.row_no) }"
                  />
                </td>
              </tr>
              <!-- Expanded diff -->
              <tr v-if="expandedRowNos.has(row.row_no)" class="diff-row">
                <td colspan="6">
                  <div class="diff-detail">
                    <div v-if="row.diff_fields && row.diff_fields.length > 0">
                      <table class="diff-table">
                        <thead>
                          <tr>
                            <th>字段</th>
                            <th>当前值</th>
                            <th>新值</th>
                            <th>处理方式</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(diff, di) in row.diff_fields" :key="di">
                            <td>{{ diff.field_label || diff.field_key }}</td>
                            <td class="diff-old">{{ diff.old_value ?? '—' }}</td>
                            <td class="diff-new">{{ diff.new_value ?? '—' }}</td>
                            <td>
                              <BaseBadge
                                type="custom"
                                :label="getStatusLabel(changeTypeLabel, diff.change_type || 'UPDATE')"
                                :color="diff.change_type === 'CONFIRMATION' ? '#D97706' : '#2563EB'"
                                :background="diff.change_type === 'CONFIRMATION' ? '#FFF7E8' : '#EFF6FF'"
                                size="sm"
                              />
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-if="row.issues && row.issues.length > 0" class="row-issues">
                      <div v-for="issue in row.issues" :key="issue.id" class="issue-item">
                        <AlertTriangle v-if="issue.severity === 'WARNING'" :size="14" class="issue-warn" />
                        <AlertCircle v-else :size="14" class="issue-error" />
                        <span>{{ issue.title }}</span>
                      </div>
                    </div>
                    <div v-if="(!row.diff_fields || row.diff_fields.length === 0) && (!row.issues || row.issues.length === 0)">
                      <span class="text-tertiary">无数据变化</span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <div class="form-actions">
          <BaseButton variant="ghost" @click="goPrev">上一步</BaseButton>
          <BaseButton variant="primary" @click="continueAfterPreview">
            继续
            <ChevronRight :size="16" />
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Step 4: Issues ===================== -->
    <div v-show="currentStep === 4 && !wizardLoading" class="step-content">
      <div class="card step-card">
        <h2 class="step-title">处理问题</h2>
        <p class="step-desc">处理导入过程中发现的问题。阻断问题必须处理才能继续。</p>

        <!-- BLOCKER issues -->
        <div v-if="blockerIssues.length > 0" class="issue-section">
          <h3 class="issue-section-title">
            <AlertCircle :size="16" class="issue-error-icon" />
            阻断问题（{{ blockerIssues.length }}）
            <span class="issue-hint">必须处理</span>
          </h3>
          <div v-for="issue in blockerIssues" :key="issue.id" class="issue-card issue-blocker">
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <BaseBadge
                type="custom"
                label="BLOCKER"
                color="#E11D48"
                background="#FFF1F2"
                size="sm"
              />
            </div>
            <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
            <div v-if="issue.old_value !== null || issue.new_value !== null" class="issue-values">
              <div v-if="issue.old_value !== null" class="issue-value-pair">
                <span class="value-label">当前值：</span>
                <span class="value-old">{{ String(issue.old_value) }}</span>
              </div>
              <div v-if="issue.new_value !== null" class="issue-value-pair">
                <span class="value-label">新值：</span>
                <span class="value-new">{{ String(issue.new_value) }}</span>
              </div>
            </div>

            <!-- Edit mode -->
            <div v-if="editingIssueId === issue.id" class="issue-edit-form">
              <div class="edit-field">
                <label>修改值</label>
                <BaseInput v-model="issueEditValue" placeholder="输入新值" />
              </div>
              <div class="edit-field">
                <label>备注（可选）</label>
                <BaseInput v-model="issueEditNote" placeholder="修改原因" />
              </div>
              <div class="edit-actions">
                <BaseButton variant="ghost" size="sm" @click="cancelIssueEdit">取消</BaseButton>
                <BaseButton variant="primary" size="sm" @click="handleIssueModifySubmit(issue)">保存</BaseButton>
              </div>
            </div>

            <!-- Action buttons -->
            <div v-else class="issue-actions">
              <button
                v-for="action in issue.allowed_actions"
                :key="action"
                class="issue-action-btn"
                :class="actionButtonInfo[action]?.variant || 'secondary'"
                @click="handleIssueAction(issue, action)"
              >
                {{ actionButtonInfo[action]?.label || action }}
              </button>
            </div>
          </div>
        </div>

        <!-- WARNING issues -->
        <div v-if="warningIssues.length > 0" class="issue-section">
          <h3 class="issue-section-title">
            <AlertTriangle :size="16" class="issue-warn-icon" />
            提醒（{{ warningIssues.length }}）
            <span class="issue-hint">可以忽略</span>
          </h3>
          <div v-for="issue in warningIssues" :key="issue.id" class="issue-card issue-warning">
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <BaseBadge
                type="custom"
                label="WARNING"
                color="#D97706"
                background="#FFF7E8"
                size="sm"
              />
            </div>
            <p v-if="issue.message" class="issue-message">{{ issue.message }}</p>
            <div v-if="issue.old_value !== null || issue.new_value !== null" class="issue-values">
              <div v-if="issue.old_value !== null" class="issue-value-pair">
                <span class="value-label">当前值：</span>
                <span class="value-old">{{ String(issue.old_value) }}</span>
              </div>
              <div v-if="issue.new_value !== null" class="issue-value-pair">
                <span class="value-label">新值：</span>
                <span class="value-new">{{ String(issue.new_value) }}</span>
              </div>
            </div>

            <div v-if="editingIssueId === issue.id" class="issue-edit-form">
              <div class="edit-field">
                <label>修改值</label>
                <BaseInput v-model="issueEditValue" placeholder="输入新值" />
              </div>
              <div class="edit-field">
                <label>备注（可选）</label>
                <BaseInput v-model="issueEditNote" placeholder="修改原因" />
              </div>
              <div class="edit-actions">
                <BaseButton variant="ghost" size="sm" @click="cancelIssueEdit">取消</BaseButton>
                <BaseButton variant="primary" size="sm" @click="handleIssueModifySubmit(issue)">保存</BaseButton>
              </div>
            </div>

            <div v-else class="issue-actions">
              <button
                v-for="action in issue.allowed_actions"
                :key="action"
                class="issue-action-btn"
                :class="actionButtonInfo[action]?.variant || 'secondary'"
                @click="handleIssueAction(issue, action)"
              >
                {{ actionButtonInfo[action]?.label || action }}
              </button>
            </div>
          </div>
        </div>

        <!-- Resolved issues -->
        <div v-if="resolvedIssues.length > 0" class="issue-section">
          <h3 class="issue-section-title">
            <Check :size="16" class="issue-resolved-icon" />
            已处理（{{ resolvedIssues.length }}）
          </h3>
          <div v-for="issue in resolvedIssues" :key="issue.id" class="issue-card issue-resolved">
            <div class="issue-header">
              <span class="issue-title">{{ issue.title }}</span>
              <span class="resolved-label">已{{ issue.resolution_action === 'ignore' ? '忽略' : '处理' }}</span>
            </div>
          </div>
        </div>

        <!-- No issues -->
        <div v-if="blockerIssues.length === 0 && warningIssues.length === 0 && resolvedIssues.length === 0">
          <BaseEmpty title="没有问题" description="所有数据正常" />
        </div>

        <div class="form-actions">
          <BaseButton variant="ghost" @click="goPrev">上一步</BaseButton>
          <BaseButton
            variant="primary"
            :disabled="!canContinueFromIssues()"
            @click="goToStep5"
          >
            继续
            <ChevronRight :size="16" />
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Step 5: Confirm ===================== -->
    <div v-show="currentStep === 5 && !wizardLoading" class="step-content">
      <div class="card step-card">
        <h2 class="step-title">确认导入</h2>
        <p class="step-desc">请确认本次导入将执行的操作。确认后不可撤销。</p>

        <div v-if="confirmationItems.length > 0" class="confirm-grid">
          <div
            v-for="item in confirmationItems"
            :key="item.label"
            class="confirm-item"
            :style="{ borderLeftColor: item.color }"
          >
            <div class="confirm-count" :style="{ color: item.color }">{{ item.count }}</div>
            <div class="confirm-label">{{ item.label }}</div>
          </div>
        </div>

        <div class="form-actions">
          <BaseButton variant="ghost" @click="goPrev">上一步</BaseButton>
          <BaseButton
            variant="primary"
            :loading="wizardLoading"
            @click="requestFirstConfirm"
          >
            <Check :size="16" />
            确认导入
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Step 6: Result ===================== -->
    <div v-show="currentStep === 6 && !wizardLoading" class="step-content">
      <div class="card step-card" :class="commitFailed ? 'result-failed' : 'result-success'">
        <div class="result-icon-wrap">
          <div v-if="commitFailed" class="result-icon result-icon-failed">
            <X :size="40" />
          </div>
          <div v-else class="result-icon result-icon-success">
            <Check :size="40" />
          </div>
        </div>

        <h2 class="result-title">
          {{ commitFailed ? '导入失败' : '导入成功' }}
        </h2>

        <p v-if="commitFailed" class="result-desc result-desc-failed">
          {{ commitErrorMessage || '系统处理失败，本次没有写入业务数据' }}
        </p>
        <p v-else class="result-desc">
          导入已完成，系统已写入业务数据。
        </p>

        <!-- Success summary -->
        <div v-if="!commitFailed && commitSummaryItems.length > 0" class="result-summary">
          <div
            v-for="item in commitSummaryItems"
            :key="item.label"
            class="result-summary-item"
          >
            <span class="result-summary-count" :style="{ color: item.color }">{{ item.count }}</span>
            <span class="result-summary-label">{{ item.label }}</span>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="result-actions">
          <BaseButton variant="ghost" @click="goBackToList">
            返回列表
          </BaseButton>
          <BaseButton variant="secondary" @click="downloadResultFile">
            <Download :size="16" />
            下载文件
          </BaseButton>
          <BaseButton variant="primary" @click="viewDetails">
            <Eye :size="16" />
            查看详情
          </BaseButton>
        </div>

        <!-- Retry for failed -->
        <div v-if="commitFailed" class="retry-section">
          <BaseButton variant="danger" :loading="wizardLoading" @click="handleCommit">
            重试导入
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- ===================== Second Confirm Modal ===================== -->
    <BaseModal
      :show="showSecondConfirm"
      title="二次确认"
      message="请再次确认本次导入操作。一旦确认，系统将开始写入业务数据。"
      confirm-text="确认提交"
      danger
      @confirm="requestSecondConfirm"
      @cancel="showSecondConfirm = false"
    />

    <!-- Confirm modal -->
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
.page-header {
  margin-bottom: 24px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  margin-bottom: 8px;
}
.back-link:hover {
  color: var(--color-primary);
}
.page-title {
  font-size: var(--font-size-lg);
  font-weight: 700;
}

/* Step Indicator */
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 28px;
  padding: 16px 24px;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}
.step-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-sm);
  font-weight: 600;
  background: var(--color-bg);
  color: var(--color-text-tertiary);
  border: 2px solid var(--color-border);
  transition: all 0.2s;
  flex-shrink: 0;
}
.step-active .step-circle {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.step-completed .step-circle {
  background: var(--color-success);
  color: #fff;
  border-color: var(--color-success);
}
.step-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  white-space: nowrap;
}
.step-active .step-label {
  color: var(--color-primary);
  font-weight: 600;
}
.step-completed .step-label {
  color: var(--color-success);
}
.step-connector {
  width: 40px;
  height: 2px;
  background: var(--color-border);
  margin: 0 12px;
  transition: background 0.2s;
}
.connector-active {
  background: var(--color-success);
}

/* Card */
.card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.step-card {
  padding: 28px 32px;
}
.step-title {
  font-size: var(--font-size-md);
  font-weight: 700;
  margin-bottom: 4px;
}
.step-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: 20px;
}

/* Form */
.form-section {
  margin-bottom: 20px;
}
.form-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text-primary);
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

/* Mode selector */
.mode-options {
  display: flex;
  gap: 12px;
}
.mode-card {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s;
}
.mode-card:hover {
  border-color: var(--color-primary);
}
.mode-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.mode-radio {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
  transition: all 0.15s;
}
.radio-checked {
  border-color: var(--color-primary);
}
.radio-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-primary);
}
.mode-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin-bottom: 2px;
}
.mode-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* Dropzone */
.dropzone {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 28px 20px;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--color-bg);
}
.dropzone:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.dropzone.has-file {
  border-style: solid;
  border-color: var(--color-success);
  background: var(--color-success-soft);
}
.file-input-hidden {
  display: none;
}
.dropzone-icon {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.has-file-icon {
  color: var(--color-success);
}
.dropzone-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dropzone-primary {
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.dropzone-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

/* Sheet list */
.sheet-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.sheet-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all 0.15s;
}
.sheet-item:hover {
  border-color: var(--color-primary);
}
.sheet-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.sheet-check {
  color: var(--color-primary);
}

/* Alert */
.alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  margin-bottom: 16px;
}
.alert-warning {
  background: var(--color-warning-soft);
  color: #B54708;
  border: 1px solid #FDE68A;
}
.alert-danger {
  background: var(--color-danger-soft);
  color: #BE123C;
  border: 1px solid #FECDD3;
}
.alert-info {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 1px solid #C7D2FE;
}

/* Mapping table */
.mapping-table-wrap {
  overflow-x: auto;
  margin-bottom: 8px;
}
.mapping-table {
  width: 100%;
  border-collapse: collapse;
}
.mapping-table th,
.mapping-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
.mapping-table th {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-secondary);
}
.col-arrow {
  width: 30px;
  text-align: center;
  color: var(--color-text-tertiary);
}
.mapping-row:hover {
  background: var(--color-bg);
}
.source-header {
  font-weight: 500;
}
.mapping-select {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  outline: none;
  background: var(--color-surface);
  cursor: pointer;
}
.mapping-select:focus {
  border-color: var(--color-primary);
}
.status-mapped {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-success);
  font-size: var(--font-size-xs);
  font-weight: 500;
}
.status-unmapped {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-warning);
  font-size: var(--font-size-xs);
  font-weight: 500;
}

/* Summary cards */
.summary-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.summary-card {
  flex: 1;
  min-width: 100px;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-top: 3px solid;
  text-align: center;
  background: var(--color-surface);
}
.summary-count {
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.2;
}
.summary-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

/* Preview */
.preview-filters {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.filter-tab {
  padding: 5px 14px;
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: var(--color-surface);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.15s;
}
.filter-tab:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.filter-tab.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.preview-table {
  width: 100%;
  border-collapse: collapse;
}
.preview-table th,
.preview-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
}
.preview-table th {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-secondary);
}
.preview-row {
  cursor: pointer;
  transition: background 0.15s;
}
.preview-row:hover {
  background: var(--color-bg);
}
.col-row {
  width: 40px;
  color: var(--color-text-tertiary);
}
.col-name {
  font-weight: 500;
}
.no-match {
  color: var(--color-text-tertiary);
}
.change-count {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
}
.expand-icon {
  transition: transform 0.15s;
  color: var(--color-text-tertiary);
}
.expand-icon.expanded {
  transform: rotate(90deg);
}
.empty-cell {
  text-align: center;
}

/* Diff detail */
.diff-row td {
  padding: 0;
  background: var(--color-bg);
}
.diff-detail {
  padding: 12px 20px;
}
.diff-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}
.diff-table th,
.diff-table td {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-xs);
}
.diff-table th {
  background: var(--color-surface);
  font-weight: 600;
  color: var(--color-text-secondary);
}
.diff-old {
  color: var(--color-text-tertiary);
}
.diff-new {
  color: var(--color-primary);
  font-weight: 500;
}
.row-issues {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.issue-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.issue-warn {
  color: var(--color-warning);
  flex-shrink: 0;
}
.issue-error {
  color: var(--color-danger);
  flex-shrink: 0;
}

/* Issues */
.issue-section {
  margin-bottom: 24px;
}
.issue-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-base);
  font-weight: 600;
  margin-bottom: 12px;
}
.issue-error-icon {
  color: var(--color-danger);
}
.issue-warn-icon {
  color: var(--color-warning);
}
.issue-resolved-icon {
  color: var(--color-success);
}
.issue-hint {
  font-size: var(--font-size-xs);
  font-weight: 400;
  color: var(--color-text-tertiary);
}
.issue-card {
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  transition: all 0.15s;
}
.issue-blocker {
  border-left: 3px solid var(--color-danger);
}
.issue-warning {
  border-left: 3px solid var(--color-warning);
}
.issue-resolved {
  border-left: 3px solid var(--color-success);
  opacity: 0.7;
}
.issue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  gap: 8px;
}
.issue-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.issue-message {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
.issue-values {
  display: flex;
  gap: 16px;
  margin-bottom: 10px;
  font-size: var(--font-size-xs);
}
.issue-value-pair {
  display: flex;
  gap: 4px;
  align-items: center;
}
.value-label {
  color: var(--color-text-tertiary);
}
.value-old {
  color: var(--color-text-secondary);
  text-decoration: line-through;
}
.value-new {
  color: var(--color-primary);
  font-weight: 500;
}
.issue-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.issue-action-btn {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
}
.issue-action-btn:hover {
  background: var(--color-bg);
}
.issue-action-btn.primary {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.issue-action-btn.primary:hover {
  background: var(--color-primary-hover);
}
.issue-action-btn.danger {
  color: var(--color-danger);
  border-color: var(--color-danger-soft);
  background: var(--color-danger-soft);
}
.issue-action-btn.danger:hover {
  background: var(--color-danger);
  color: #fff;
}
.issue-action-btn.ghost {
  border-color: transparent;
  background: transparent;
}
.resolved-label {
  font-size: var(--font-size-xs);
  color: var(--color-success);
  font-weight: 500;
}
.issue-edit-form {
  margin-top: 10px;
  padding: 12px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.edit-field label {
  display: block;
  font-size: var(--font-size-xs);
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--color-text-secondary);
}
.edit-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

/* Confirm */
.confirm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.confirm-item {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-left: 3px solid;
  background: var(--color-surface);
}
.confirm-count {
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.2;
}
.confirm-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

/* Result */
.result-success {
  text-align: center;
}
.result-failed {
  text-align: center;
}
.result-icon-wrap {
  margin-bottom: 16px;
}
.result-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.result-icon-success {
  background: var(--color-success-soft);
  color: var(--color-success);
}
.result-icon-failed {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.result-title {
  font-size: var(--font-size-lg);
  font-weight: 700;
  margin-bottom: 8px;
}
.result-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: 20px;
  max-width: 480px;
  margin-left: auto;
  margin-right: auto;
}
.result-desc-failed {
  color: var(--color-danger);
}
.result-summary {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.result-summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.result-summary-count {
  font-size: var(--font-size-xl);
  font-weight: 700;
}
.result-summary-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.result-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.retry-section {
  margin-top: 8px;
}

/* Loading overlay */
.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 64px;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
.spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Utility */
.text-danger {
  color: var(--color-danger);
}
.text-tertiary {
  color: var(--color-text-tertiary);
}
</style>
