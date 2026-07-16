<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string | number
  placeholder?: string
  disabled?: boolean
  type?: 'text' | 'date' | 'number'
}>(), {
  type: 'text',
  placeholder: '',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const inputRef = ref<HTMLInputElement>()

function handleInput(e: Event) {
  const target = e.target as HTMLInputElement
  emit('update:modelValue', target.value)
}

defineExpose({ focus: () => inputRef.value?.focus() })
</script>

<template>
  <input
    ref="inputRef"
    class="base-input"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    @input="handleInput"
  />
</template>

<style scoped>
.base-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  background: var(--color-surface);
  transition: border-color 0.2s;
  outline: none;
}
.base-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}
.base-input::placeholder {
  color: var(--color-text-tertiary);
}
.base-input:disabled {
  background: var(--color-bg);
  cursor: not-allowed;
}
</style>
