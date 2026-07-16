<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  name?: string
  size?: 'sm' | 'md' | 'lg'
}>(), {
  size: 'md',
})

const bgColor = computed(() => {
  if (!props.name) return '#E6E8F0'
  let hash = 0
  for (let i = 0; i < props.name.length; i++) {
    hash = props.name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const colors = [
    '#4F46E5', '#2563EB', '#0F9F94', '#D97706',
    '#E11D48', '#7C3AED', '#16825D', '#C01048',
  ]
  return colors[Math.abs(hash) % colors.length]
})

const initial = computed(() => {
  if (!props.name) return '?'
  return props.name.charAt(0).toUpperCase()
})

const sizeMap = { sm: 28, md: 36, lg: 48 }
const fontSizeMap = { sm: 12, md: 15, lg: 20 }
</script>

<template>
  <div
    class="emp-avatar"
    :style="{
      width: sizeMap[size] + 'px',
      height: sizeMap[size] + 'px',
      background: bgColor,
      fontSize: fontSizeMap[size] + 'px',
    }"
    :title="name"
  >
    {{ initial }}
  </div>
</template>

<style scoped>
.emp-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
  font-weight: 600;
  flex-shrink: 0;
  user-select: none;
}
</style>
