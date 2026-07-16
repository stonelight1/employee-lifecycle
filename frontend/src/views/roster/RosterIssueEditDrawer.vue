<script setup lang="ts">
import { ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import type { IssueItem } from '@/types/roster-import'

const props = defineProps<{
  issue: IssueItem | null
  show: boolean
}>()

const emit = defineEmits<{
  'modify-submit': [issue: IssueItem, value: string, note: string]
  close: []
}>()

const editValue = ref('')
const editNote = ref('')

watch(() => props.issue, (issue) => {
  if (issue) {
    editValue.value = String(issue.new_value ?? issue.system_value ?? '')
    editNote.value = ''
  }
})

function handleSubmit() {
  if (!props.issue || !editValue.value.trim()) return
  emit('modify-submit', props.issue, editValue.value, editNote.value)
}

function handleCancel() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="show && issue" class="drawer-overlay" @click.self="emit('close')">
        <div class="drawer-panel">
          <div class="drawer-header">
            <h3 class="drawer-title">修改问题</h3>
            <button class="drawer-close" @click="emit('close')">✕</button>
          </div>
          <div class="drawer-body">
            <div class="info-section">
              <div class="info-row"><span class="info-label">员工</span><span class="info-value">{{ issue.employee_name || '—' }}</span></div>
              <div class="info-row"><span class="info-label">问题</span><span class="info-value">{{ issue.title }}</span></div>
              <div class="info-row"><span class="info-label">说明</span><span class="info-value">{{ issue.message || '—' }}</span></div>
              <div class="info-row"><span class="info-label">Excel原值</span><span class="info-value mono">{{ issue.source_value ?? issue.old_value ?? '—' }}</span></div>
              <div class="info-row"><span class="info-label">系统建议</span><span class="info-value mono">{{ issue.system_value ?? issue.new_value ?? '—' }}</span></div>
            </div>

            <div v-if="issue.recommendation_text" class="recommendation-box">
              <span class="rec-label">推荐：</span>
              <span class="rec-text">{{ issue.recommendation_text }}</span>
            </div>

            <div class="edit-section">
              <div class="form-field">
                <label>修改值</label>
                <BaseInput v-model="editValue" placeholder="输入新值" />
              </div>
              <div class="form-field">
                <label>备注</label>
                <BaseInput v-model="editNote" placeholder="修改原因（选填）" />
              </div>
            </div>
          </div>
          <div class="drawer-footer">
            <BaseButton variant="ghost" @click="handleCancel">取消</BaseButton>
            <BaseButton variant="primary" :disabled="!editValue.trim()" @click="handleSubmit">保存</BaseButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 1000; display: flex; justify-content: flex-end; }
.drawer-panel { width: 480px; max-width: 90vw; background: var(--color-surface); height: 100%; display: flex; flex-direction: column; box-shadow: -4px 0 16px rgba(0,0,0,0.1); }
.drawer-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--color-border); }
.drawer-title { font-size: var(--font-size-base); font-weight: 600; margin: 0; }
.drawer-close { background: none; border: none; cursor: pointer; font-size: 18px; color: var(--color-text-secondary); padding: 4px; }
.drawer-body { flex: 1; overflow-y: auto; padding: 20px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid var(--color-border); }
.info-section { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.info-row { display: flex; gap: 8px; font-size: var(--font-size-sm); }
.info-label { width: 80px; flex-shrink: 0; color: var(--color-text-secondary); }
.info-value { flex: 1; word-break: break-all; }
.info-value.mono { font-family: monospace; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.recommendation-box { padding: 10px 12px; background: var(--color-bg); border-radius: var(--radius-sm); margin-bottom: 16px; border-left: 3px solid var(--color-primary); font-size: var(--font-size-sm); }
.rec-label { font-weight: 600; color: var(--color-primary); }
.rec-text { color: var(--color-text-secondary); }
.edit-section { display: flex; flex-direction: column; gap: 12px; }
.form-field label { display: block; font-size: var(--font-size-xs); font-weight: 500; margin-bottom: 4px; color: var(--color-text-secondary); }

.drawer-enter-active, .drawer-leave-active { transition: all 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-panel, .drawer-leave-to .drawer-panel { transform: translateX(100%); }
</style>
