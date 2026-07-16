<script setup lang="ts">
withDefaults(defineProps<{
  rows?: number
  type?: 'table' | 'card' | 'text'
}>(), {
  rows: 3,
  type: 'text',
})
</script>

<template>
  <div v-if="type === 'text'" class="skeleton-text">
    <div v-for="i in rows" :key="i" class="skeleton-line" :style="{ width: `${80 - i * 10}%` }" />
  </div>
  <div v-else-if="type === 'table'" class="skeleton-table">
    <div class="skeleton-row" v-for="i in rows" :key="i">
      <div class="skeleton-cell" v-for="j in 5" :key="j" />
    </div>
  </div>
  <div v-else class="skeleton-card">
    <div class="skeleton-card-line" v-for="i in rows" :key="i" />
  </div>
</template>

<style scoped>
.skeleton-line,
.skeleton-cell,
.skeleton-card-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--color-bg) 25%, var(--color-border) 50%, var(--color-bg) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-text {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-line {
  height: 14px;
}

.skeleton-table {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.skeleton-row {
  display: flex;
  gap: 16px;
}
.skeleton-cell {
  flex: 1;
  height: 14px;
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-card-line {
  height: 14px;
}
</style>
