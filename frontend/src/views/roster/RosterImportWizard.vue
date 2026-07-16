<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ChevronLeft, Check, Loader2 } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import BaseModal from '@/components/base/BaseModal.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import PageHeader from '@/components/layout/PageHeader.vue'

import RosterUploadStep from './RosterUploadStep.vue'
import RosterMappingStep from './RosterMappingStep.vue'
import RosterPreviewStep from './RosterPreviewStep.vue'
import RosterIssueStep from './RosterIssueStep.vue'
import RosterCommitStep from './RosterCommitStep.vue'
import RosterResultStep from './RosterResultStep.vue'

import {
  uploadRoster,
  saveMapping,
  generatePreview,
  getBatchIssues,
  resolveIssue,
  batchResolveIssues,
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
  CommitResponse,
} from '@/types/roster-import'

const router = useRouter()
const route = useRoute()
const { showToast } = useToast()
const { show: showConfirm, options: confirmOpts, confirm, handleConfirm, handleCancel } = useConfirm()

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

// ===================== Shared State =====================
const uploadResult = ref<RosterUploadResponse | null>(null)
const batchId = computed(() => {
  // 优先使用上传结果中的 batch_id
  if (uploadResult.value?.batch_id) return uploadResult.value.batch_id
  // 支持从 query params 传入已有批次 ID
  const qid = route.query.batch_id
  if (qid) return Number(qid)
  return null
})
const hasExistingInitBatch = ref(false)

// Upload step state
const selectedFile = ref<File | null>(null)
const uploadMode = ref<'INITIALIZE' | 'SYNC'>('SYNC')
const sheetNames = ref<string[]>([])
const selectedSheet = ref('')
const isDuplicate = ref(false)
const existingBatchId = ref<number | null>(null)

// Mapping step state
const columnMappings = ref<ColumnMapping[]>([])
const fieldDefinitions = ref<FieldDefinition[]>([])
const mappingBatchId = ref<number | null>(null)

// Preview step state
const previewData = ref<PreviewResponse | null>(null)
const previewRows = ref<RowPreviewItem[]>([])

// Issue step state
const issues = ref<IssueItem[]>([])

// Commit step state
const showSecondConfirm = ref(false)

// Result step state
const commitResult = ref<CommitResponse | null>(null)
const commitFailed = ref(false)
const commitErrorMessage = ref('')

// ===================== Computed =====================
const unmappedRequiredFields = computed(() => {
  const requiredKeys = fieldDefinitions.value.filter(fd => fd.required).map(fd => fd.key)
  const mappedKeys = columnMappings.value
    .filter(cm => cm.target_field_key)
    .map(cm => cm.target_field_key)
  return requiredKeys.filter(key => !mappedKeys.includes(key))
})

// ===================== Step 1: Upload =====================
async function handleUpload() {
  if (!selectedFile.value) return
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
    if (result.suggestion === 'duplicate_batch') {
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

function onFileChange(file: File | null) {
  selectedFile.value = file
  uploadResult.value = null
  sheetNames.value = []
  selectedSheet.value = ''
  isDuplicate.value = false
  existingBatchId.value = null
  resetBatchState()
}

// ===================== Step 2: Mapping =====================
async function loadMapping() {
  if (!batchId.value) return
  wizardLoading.value = true
  try {
    const detail = await getBatchDetail(batchId.value)
    const defs = await getFieldDefinitions()
    fieldDefinitions.value = defs
    columnMappings.value = normalizeColumnMappings(detail, defs)
    mappingBatchId.value = batchId.value
  } catch (e: any) {
    showToast({ message: e.message || '加载映射失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

function normalizeColumnMappings(detail: any, defs: FieldDefinition[]): ColumnMapping[] {
  const raw = detail.column_mappings || detail.mappings || []
  const requiredKeys = new Set(defs.filter(fd => fd.required).map(fd => fd.key))

  if (Array.isArray(raw)) {
    return raw.map((item: any) => {
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
    }).filter(Boolean) as ColumnMapping[]
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
  if (!batchId.value) return
  if (unmappedRequiredFields.value.length > 0) return

  wizardLoading.value = true
  try {
    const mappings: Record<string, string | null> = {}
    columnMappings.value.forEach(m => { mappings[m.source_header] = m.target_field_key })
    await saveMapping(batchId.value, { mappings })
    showToast({ message: '映射保存成功', type: 'success' })
    currentStep.value = 3
  } catch (e: any) {
    showToast({ message: e.message || '保存映射失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

// ===================== Step 3: Preview =====================
async function handleLoadPreview() {
  if (!batchId.value || previewData.value) return
  wizardLoading.value = true
  try {
    const data = await generatePreview(batchId.value)
    previewData.value = data
    previewRows.value = data.rows || []
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
async function loadIssues() {
  if (!batchId.value) return
  wizardLoading.value = true
  try {
    const data = await getBatchIssues(batchId.value)
    issues.value = data.items || []
  } catch (e: any) {
    showToast({ message: e.message || '加载问题失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

async function handleIssueAction(issue: IssueItem, action: string) {
  if (!batchId.value) return
  wizardLoading.value = true
  try {
    const payload: any = { action }
    if ((action === 'ACCEPT' || action === 'MODIFY_VALUE') && issue.new_value !== undefined) {
      payload.value = issue.new_value
    }
    await resolveIssue(batchId.value, issue.id, payload)
    showToast({ message: '问题已处理', type: 'success' })
    await loadIssues()
  } catch (e: any) {
    showToast({ message: e.message || '处理失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

async function handleIssueModifySubmit(issue: IssueItem, value: string, note: string) {
  if (!batchId.value) return
  wizardLoading.value = true
  try {
    // MODIFY_VALUE 需要 {field_key, new_value} 格式的 value
    const modifyValue = { field_key: issue.field_key || '', new_value: value }
    await resolveIssue(batchId.value, issue.id, { action: 'MODIFY_VALUE', value: modifyValue, note: note || undefined })
    showToast({ message: '修改已保存', type: 'success' })
    await loadIssues()
  } catch (e: any) {
    showToast({ message: e.message || '修改失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

async function handleBatchResolve(issueIds: number[], resolveAction: string) {
  if (!batchId.value || issueIds.length === 0) return
  wizardLoading.value = true
  try {
    const result = await batchResolveIssues(batchId.value, { issue_ids: issueIds, action: resolveAction as 'APPLY_RECOMMENDATION' | 'IGNORE' })
    if (result.conflicts && result.conflicts.length > 0) {
      showToast({ message: `${result.resolved}条处理成功，${result.conflicts.length}条因冲突跳过`, type: 'warning' })
    } else {
      showToast({ message: `${result.resolved}条问题已处理`, type: 'success' })
    }
    await loadIssues()
  } catch (e: any) {
    showToast({ message: e.message || '批量处理失败', type: 'error' })
  } finally {
    wizardLoading.value = false
  }
}

function canContinueFromIssues(): boolean {
  const blockers = issues.value.filter(i => i.severity === 'BLOCKER')
  return blockers.every(i => i.resolution_status !== 'PENDING')
}

// ===================== Step 5: Commit =====================
function requestSecondConfirm() {
  showSecondConfirm.value = false
  confirm({
    title: '确认导入',
    message: '确认提交本次导入？导入产生的部分操作可以通过导入记录撤销；已经由 HR 确认的合同、银行卡等业务操作不会随批次撤销。',
    confirmText: '确认导入',
    danger: true,
    onConfirm: () => handleCommit(),
  })
}

// ===================== Step 6: Result =====================
async function handleCommit() {
  if (!batchId.value) return
  wizardLoading.value = true
  commitFailed.value = false
  commitErrorMessage.value = ''
  try {
    const result = await commitImport(batchId.value)
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

// ===================== Navigation =====================
function goNext() {
  if (currentStep.value === 1 && uploadResult.value) currentStep.value = 2
  else if (currentStep.value === 2) handleSaveMapping()
  else if (currentStep.value === 3) continueAfterPreview()
  else if (currentStep.value === 4 && canContinueFromIssues()) currentStep.value = 5
  else if (currentStep.value === 5) requestSecondConfirm()
}

function goPrev() {
  if (currentStep.value > 1) currentStep.value--
}

function goBackToList() {
  if (route.query.from === 'employees') router.push('/employees')
  else router.push('/roster-imports')
}

function viewDetails() {
  if (batchId.value) router.push(`/roster-imports/${batchId.value}`)
}

function downloadResultFile() {
  if (batchId.value) window.open(getFileDownloadUrl(batchId.value), '_blank')
}

function resetBatchState() {
  columnMappings.value = []
  fieldDefinitions.value = []
  mappingBatchId.value = null
  previewData.value = null
  previewRows.value = []
  issues.value = []
}

// ===================== Init =====================
onMounted(async () => {
  // 如果从 query params 传入已有批次 ID，直接跳到问题处理步骤
  const qid = route.query.batch_id
  if (qid && !isNaN(Number(qid))) {
    // 模拟 uploadResult 让 batchId 计算属性生效
    uploadResult.value = { batch_id: Number(qid) } as any
    // 直接跳到步骤 4（问题处理），watch 会自动加载映射、预览和问题
    currentStep.value = 4
  }
  pageLoading.value = false
})

// Watchers
watch(currentStep, async (step) => {
  if (step === 2 && batchId.value && mappingBatchId.value !== batchId.value) await loadMapping()
  if (step === 3 && !previewData.value) await handleLoadPreview()
  if (step === 4 && issues.value.length === 0) await loadIssues()
})
</script>

<template>
  <div class="page">
    <PageHeader
      title="花名册导入向导"
      :show-back="true"
      @back="goBackToList"
    />

    <!-- Step indicator -->
    <div class="step-indicator">
      <div v-for="(step, idx) in steps" :key="step.num" class="step-item"
        :class="{ 'step-active': currentStep === step.num, 'step-completed': currentStep > step.num }">
        <div class="step-circle">
          <Check v-if="currentStep > step.num" :size="14" />
          <span v-else>{{ step.num }}</span>
        </div>
        <span class="step-label">{{ step.title }}</span>
        <div v-if="idx < steps.length - 1" class="step-connector" :class="{ 'connector-active': currentStep > step.num }" />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="wizardLoading" class="loading-overlay">
      <Loader2 :size="32" class="spinner" />
      <span>处理中...</span>
    </div>

    <!-- Step 1: Upload -->
    <RosterUploadStep v-show="currentStep === 1 && !wizardLoading"
      :selected-file="selectedFile"
      :upload-mode="uploadMode"
      :sheet-names="sheetNames"
      :selected-sheet="selectedSheet"
      :upload-result="uploadResult"
      :is-duplicate="isDuplicate"
      :existing-batch-id="existingBatchId"
      :loading="wizardLoading"
      :has-existing-init-batch="hasExistingInitBatch"
      @update:upload-mode="uploadMode = $event"
      @update:selected-sheet="selectedSheet = $event"
      @file-change="onFileChange"
      @upload="handleUpload"
      @cancel="goBackToList"
    />

    <!-- Step 2: Mapping -->
    <RosterMappingStep v-show="currentStep === 2 && !wizardLoading"
      :column-mappings="columnMappings"
      :field-definitions="fieldDefinitions"
      :unmapped-required-fields="unmappedRequiredFields"
      :loading="wizardLoading"
      @update-mapping="updateMapping"
      @save="handleSaveMapping"
      @prev="goPrev"
    />

    <!-- Step 3: Preview -->
    <RosterPreviewStep v-show="currentStep === 3 && !wizardLoading"
      :preview-data="previewData"
      :preview-rows="previewRows"
      :loading="wizardLoading"
      @continue="continueAfterPreview"
      @prev="goPrev"
    />

    <!-- Step 4: Issues -->
    <RosterIssueStep v-show="currentStep === 4 && !wizardLoading"
      :issues="issues"
      :loading="wizardLoading"
      @resolve="handleIssueAction"
      @modify-submit="handleIssueModifySubmit"
      @batch-resolve="handleBatchResolve"
      @continue="() => currentStep = 5"
      @prev="goPrev"
    />

    <!-- Step 5: Commit -->
    <RosterCommitStep v-show="currentStep === 5 && !wizardLoading"
      :preview-data="previewData"
      :loading="wizardLoading"
      @confirm="requestSecondConfirm"
      @prev="goPrev"
    />

    <!-- Step 6: Result -->
    <RosterResultStep v-show="currentStep === 6 && !wizardLoading"
      :commit-result="commitResult"
      :commit-failed="commitFailed"
      :commit-error-message="commitErrorMessage"
      :batch-id="batchId"
      :loading="wizardLoading"
      @retry="handleCommit"
      @view-details="viewDetails"
      @download-file="downloadResultFile"
      @back-to-list="goBackToList"
    />

    <!-- Confirm modal -->
    <BaseModal
      :show="showConfirm"
      :title="confirmOpts?.title || '确认'"
      :message="confirmOpts?.message || ''"
      :confirm-text="confirmOpts?.confirmText || '确认'"
      :danger="confirmOpts?.danger"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>

<style scoped>
.step-indicator { display: flex; align-items: center; justify-content: center; gap: 0; margin-bottom: 28px; padding: 16px 24px; background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.step-item { display: flex; align-items: center; gap: 8px; position: relative; }
.step-circle { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-sm); font-weight: 600; background: var(--color-bg); color: var(--color-text-tertiary); border: 2px solid var(--color-border); transition: all 0.2s; flex-shrink: 0; }
.step-active .step-circle { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.step-completed .step-circle { background: var(--color-success); color: #fff; border-color: var(--color-success); }
.step-label { font-size: var(--font-size-sm); color: var(--color-text-tertiary); white-space: nowrap; }
.step-active .step-label { color: var(--color-primary); font-weight: 600; }
.step-completed .step-label { color: var(--color-success); }
.step-connector { width: 40px; height: 2px; background: var(--color-border); margin: 0 12px; transition: background 0.2s; }
.connector-active { background: var(--color-success); }
.loading-overlay { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 64px; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.spinner { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
