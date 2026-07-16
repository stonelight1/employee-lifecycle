<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const navItems = [
  { path: '/employees', label: '员工管理', icon: '👥' },
  { path: '/followup-tasks', label: '跟进任务', icon: '📋' },
  { path: '/followup-nodes', label: '节点配置', icon: '⚙️' },
  { path: '/todos', label: '待办事项', icon: '✅' },
  { path: '/operation-logs', label: '操作日志', icon: '📝' },
]

function isActive(path: string) {
  return route.path.startsWith(path)
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">员工生命周期</div>
      <nav class="nav">
        <div
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="router.push(item.path)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </div>
      </nav>
    </aside>
    <main class="main">
      <header class="header">
        <h2>{{ navItems.find((n) => isActive(n.path))?.label || '员工生命周期管理系统' }}</h2>
        <div class="user-info">本地 HR</div>
      </header>
      <div class="content">
        <slot />
      </div>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 220px;
  background: #1d2b3a;
  color: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.logo {
  padding: 20px;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.nav {
  padding: 12px 0;
}
.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  transition: background 0.2s;
  color: rgba(255, 255, 255, 0.8);
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.nav-item.active {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}
.nav-icon {
  margin-right: 10px;
  font-size: 18px;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.header h2 {
  font-size: 18px;
  font-weight: 600;
}
.user-info {
  font-size: 14px;
  color: #666;
}
.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
</style>
