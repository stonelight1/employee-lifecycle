<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
import BaseToast from '@/components/base/BaseToast.vue'
</script>

<template>
  <div class="app-layout">
    <AppSidebar />
    <div class="app-main">
      <AppTopbar />
      <main class="app-content">
        <slot />
      </main>
    </div>
    <BaseToast />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.app-content {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  max-width: 1600px;
  width: 100%;
}

@media (max-width: 1280px) {
  .app-content {
    padding: 24px;
  }
}
</style>
