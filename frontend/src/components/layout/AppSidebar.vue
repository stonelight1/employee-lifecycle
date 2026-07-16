<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  ListTodo,
  Users,
  Timer,
  ArrowUpCircle,
  ArrowLeftRight,
  Settings,
  FileText,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()

const collapsed = ref(false)

interface NavItem {
  path: string
  label: string
  icon: any
}

interface NavGroup {
  title: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    title: '工作',
    items: [
      { path: '/dashboard', label: '工作台', icon: LayoutDashboard },
      { path: '/work-items', label: '工作事项', icon: ListTodo },
    ],
  },
  {
    title: '员工',
    items: [
      { path: '/employees', label: '员工中心', icon: Users },
      { path: '/probation', label: '试用期', icon: Timer },
      { path: '/regularizations', label: '转正管理', icon: ArrowUpCircle },
      { path: '/employee-movements', label: '异动与离职', icon: ArrowLeftRight },
    ],
  },
  {
    title: '系统',
    items: [
      { path: '/followup-nodes', label: '节点配置', icon: Settings },
      { path: '/operation-logs', label: '操作日志', icon: FileText },
    ],
  },
]

function isActive(path: string) {
  if (path === '/dashboard') return route.path === '/dashboard'
  return route.path.startsWith(path)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-logo">
      <span v-if="!collapsed" class="logo-text">Lifecycle Flow</span>
      <span v-else class="logo-icon" aria-label="Lifecycle Flow">LF</span>
    </div>

    <nav class="sidebar-nav">
      <div v-for="group in navGroups" :key="group.title" class="nav-group">
        <div v-if="!collapsed" class="nav-group-title">{{ group.title }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          :title="collapsed ? item.label : ''"
        >
          <component :is="item.icon" :size="20" class="nav-icon" />
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <button class="collapse-btn" :title="collapsed ? '展开' : '折叠'" @click="toggleCollapse">
        <component :is="collapsed ? ChevronRight : ChevronLeft" :size="16" />
      </button>
      <span v-if="!collapsed" class="version-text">v0.4.0</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease, min-width 0.2s ease;
  height: 100vh;
  position: sticky;
  top: 0;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
}

.sidebar-logo {
  height: 72px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}
.logo-icon {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}

.nav-group {
  margin-bottom: 8px;
}

.nav-group-title {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  padding: 8px 20px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: var(--color-text-secondary);
  transition: all 0.15s;
  position: relative;
  margin: 0 8px;
  border-radius: var(--radius-sm);
  text-decoration: none;
}
.nav-item:hover {
  background: var(--color-bg);
  color: var(--color-text-primary);
}
.nav-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 500;
}

.nav-icon {
  flex-shrink: 0;
  display: flex;
}

.nav-label {
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 8px;
}
.collapse-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  padding: 4px 6px;
  color: var(--color-text-tertiary);
  display: flex;
  align-items: center;
}
.collapse-btn:hover {
  background: var(--color-bg);
  color: var(--color-text-primary);
}
.version-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}
</style>
