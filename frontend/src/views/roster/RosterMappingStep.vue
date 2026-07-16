<script setup lang="ts">
import { ArrowRight, Check, AlertCircle } from 'lucide-vue-next'
import BaseButton from '@/components/base/BaseButton.vue'
import type { ColumnMapping, FieldDefinition } from '@/types/roster-import'

defineProps<{
  columnMappings: ColumnMapping[]
  fieldDefinitions: FieldDefinition[]
  unmappedRequiredFields: string[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update-mapping': [header: string, fieldKey: string]
  save: []
  prev: []
}>()

function updateMapping(header: string, fieldKey: string) {
  emit('update-mapping', header, fieldKey)
}
</script>

<template>
  <div class="step-content">
    <div class="card step-card">
      <h2 class="step-title">字段映射</h2>
      <p class="step-desc">确认 Excel 列与系统字段的对应关系。<span class="text-danger">*</span> 为必填字段。</p>

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
            <tr v-for="mapping in columnMappings" :key="mapping.source_header" class="mapping-row">
              <td class="col-header">
                <span class="source-header">{{ mapping.source_header }}</span>
              </td>
              <td class="col-arrow"><ArrowRight :size="14" /></td>
              <td class="col-target">
                <select
                  :value="mapping.target_field_key || ''"
                  class="mapping-select"
                  @change="updateMapping(mapping.source_header, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">— 不映射 —</option>
                  <optgroup label="系统字段">
                    <option v-for="fd in fieldDefinitions" :key="fd.key" :value="fd.key">
                      {{ fd.label }}{{ fd.required ? ' *' : '' }}
                    </option>
                  </optgroup>
                </select>
              </td>
              <td class="col-status">
                <span v-if="mapping.target_field_key" class="status-mapped"><Check :size="12" /> 已映射</span>
                <span v-else class="status-unmapped"><AlertCircle :size="12" /> 未映射</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="form-actions">
        <BaseButton variant="ghost" @click="emit('prev')">上一步</BaseButton>
        <BaseButton variant="primary" :disabled="unmappedRequiredFields.length > 0" :loading="loading" @click="emit('save')">
          <Check :size="16" /> 保存映射并继续
        </BaseButton>
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
.alert { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: var(--radius-sm); font-size: var(--font-size-sm); margin-bottom: 16px; }
.alert-danger { background: var(--color-danger-soft); color: #BE123C; border: 1px solid #FECDD3; }
.mapping-table-wrap { overflow-x: auto; margin-bottom: 8px; }
.mapping-table { width: 100%; border-collapse: collapse; }
.mapping-table th, .mapping-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.mapping-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.col-arrow { width: 30px; text-align: center; color: var(--color-text-tertiary); }
.mapping-row:hover { background: var(--color-bg); }
.source-header { font-weight: 500; }
.mapping-select { width: 100%; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-sm); outline: none; background: var(--color-surface); cursor: pointer; }
.mapping-select:focus { border-color: var(--color-primary); }
.status-mapped { display: inline-flex; align-items: center; gap: 4px; color: var(--color-success); font-size: var(--font-size-xs); font-weight: 500; }
.status-unmapped { display: inline-flex; align-items: center; gap: 4px; color: var(--color-warning); font-size: var(--font-size-xs); font-weight: 500; }
.text-danger { color: var(--color-danger); }
</style>
