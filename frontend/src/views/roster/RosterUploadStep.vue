<script setup lang="ts">
import { ref } from 'vue'
import { Upload, FileText, List, Check, AlertTriangle, ChevronLeft } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import type { RosterUploadResponse } from '@/types/roster-import'

const props = defineProps<{
  selectedFile: File | null
  uploadMode: 'INITIALIZE' | 'SYNC'
  sheetNames: string[]
  selectedSheet: string
  uploadResult: RosterUploadResponse | null
  isDuplicate: boolean
  existingBatchId: number | null
  loading: boolean
  hasExistingInitBatch: boolean
}>()

const emit = defineEmits<{
  'update:uploadMode': [value: 'INITIALIZE' | 'SYNC']
  'update:selectedSheet': [value: string]
  'file-change': [file: File | null]
  upload: []
  cancel: []
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)

const modeOptions = [
  { label: '后续同步（SYNC）', value: 'SYNC' as const },
  { label: '首次初始化（INITIALIZE）', value: 'INITIALIZE' as const },
]

const modeDescriptions: Record<string, string> = {
  SYNC: '更新已有员工信息，新增员工入职，自动更新允许的字段',
  INITIALIZE: '首次将花名册整体导入系统，建立初始档案和任职记录',
}

function onFileChange() {
  if (!fileInputRef.value?.files?.length) return
  emit('file-change', fileInputRef.value.files[0])
}

function onDropzoneClick() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div class="step-content">
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
            @click="emit('update:uploadMode', modeOpt.value)"
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
        <!-- INITIALIZE warning when batches exist -->
        <div v-if="uploadMode === 'INITIALIZE' && hasExistingInitBatch" class="alert alert-warning" style="margin-top: 8px;">
          <AlertTriangle :size="16" />
          <span>系统已有成功导入的批次，再次选择「首次初始化」可能导致数据重复。请确认操作。</span>
        </div>
      </div>

      <!-- File upload -->
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
            @change="onFileChange"
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

      <!-- Sheet selector -->
      <div v-if="sheetNames.length > 0" class="form-section">
        <label class="form-label">工作表</label>
        <div class="sheet-list">
          <div
            v-for="sheet in sheetNames"
            :key="sheet"
            class="sheet-item"
            :class="{ 'sheet-selected': selectedSheet === sheet }"
            @click="emit('update:selectedSheet', sheet)"
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
        <span>此文件已经导入过，请查看原导入记录。</span>
      </div>

      <!-- Actions -->
      <div class="form-actions">
        <BaseButton variant="ghost" @click="emit('cancel')">取消</BaseButton>
        <BaseButton
          variant="primary"
          :disabled="!selectedFile || isDuplicate"
          :loading="loading"
          @click="emit('upload')"
        >
          <Upload :size="16" />
          上传并继续
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); }
.step-card { padding: 28px 32px; }
.step-title { font-size: var(--font-size-md); font-weight: 700; margin-bottom: 4px; }
.form-section { margin-bottom: 20px; }
.form-label { display: block; font-size: var(--font-size-sm); font-weight: 600; margin-bottom: 8px; color: var(--color-text-primary); }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.mode-options { display: flex; gap: 12px; }
.mode-card { flex: 1; display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; }
.mode-card:hover { border-color: var(--color-primary); }
.mode-selected { border-color: var(--color-primary); background: var(--color-primary-soft); }
.mode-radio { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--color-border); display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
.radio-checked { border-color: var(--color-primary); }
.radio-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--color-primary); }
.mode-title { font-size: var(--font-size-sm); font-weight: 600; margin-bottom: 2px; }
.mode-desc { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.dropzone { display: flex; align-items: center; gap: 16px; padding: 28px 20px; border: 2px dashed var(--color-border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; background: var(--color-bg); }
.dropzone:hover { border-color: var(--color-primary); background: var(--color-primary-soft); }
.dropzone.has-file { border-style: solid; border-color: var(--color-success); background: var(--color-success-soft); }
.file-input-hidden { display: none; }
.dropzone-icon { color: var(--color-text-tertiary); flex-shrink: 0; }
.has-file-icon { color: var(--color-success); }
.dropzone-text { display: flex; flex-direction: column; gap: 2px; }
.dropzone-primary { font-size: var(--font-size-sm); font-weight: 500; }
.dropzone-hint { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }
.sheet-list { display: flex; gap: 8px; flex-wrap: wrap; }
.sheet-item { display: flex; align-items: center; gap: 6px; padding: 8px 14px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); cursor: pointer; font-size: var(--font-size-sm); transition: all 0.15s; }
.sheet-item:hover { border-color: var(--color-primary); }
.sheet-selected { border-color: var(--color-primary); background: var(--color-primary-soft); color: var(--color-primary); }
.sheet-check { color: var(--color-primary); }
.alert { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: var(--radius-sm); font-size: var(--font-size-sm); margin-bottom: 16px; }
.alert-warning { background: var(--color-warning-soft); color: #B54708; border: 1px solid #FDE68A; }
</style>
