<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useToast } from '@/composables/useToast'

interface NavGroup {
  title: string
  items: NavItem[]
}

interface NavItem {
  path: string
  label: string
  icon: string
}

const router = useRouter()
const route = useRoute()

const collapsed = ref(false)

const navGroups: NavGroup[] = [
  {
    title: '工作',
    items: [
      { path: '/dashboard', label: '工作台', icon: 'LayoutDashboard' },
      { path: '/work-items', label: '工作事项', icon: 'ClipboardList' },
    ],
  },
  {
    title: '员工',
    items: [
      { path: '/employees', label: '员工中心', icon: 'Users' },
      { path: '/probation', label: '试用期', icon: 'Timer' },
      { path: '/regularizations', label: '转正管理', icon: 'ArrowUpCircle' },
      { path: '/employee-movements', label: '异动与离职', icon: 'Move' },
    ],
  },
  {
    title: '系统',
    items: [
      { path: '/followup-nodes', label: '节点配置', icon: 'Settings' },
      { path: '/operation-logs', label: '操作日志', icon: 'FileText' },
    ],
  },
]

function isActive(path: string) {
  if (path === '/dashboard') return route.path === '/dashboard'
  return route.path.startsWith(path)
}

function navigate(path: string) {
  router.push(path)
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
        <div
          v-for="item in group.items"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          :title="collapsed ? item.label : ''"
          @click="navigate(item.path)"
        >
          <span class="nav-icon" v-html="iconSvg(item.icon)" />
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
        </div>
      </div>
    </nav>

    <div class="sidebar-footer">
      <button class="collapse-btn" :title="collapsed ? '展开' : '折叠'" @click="toggleCollapse">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path v-if="!collapsed" d="M15 18l-6-6 6-6" />
          <path v-else d="M9 18l6-6-6-6" />
        </svg>
      </button>
      <span v-if="!collapsed" class="version-text">v0.3.0</span>
    </div>
  </aside>
</template>

<script lang="ts">
// Icon SVG helper - renders inline SVG for lucide icons
function iconSvg(name: string): string {
  const icons: Record<string, string> = {
    LayoutDashboard: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>',
    ClipboardList: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/></svg>',
    Users: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>',
    Timer: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    ArrowUpCircle: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="16 12 12 8 8 12"/><line x1="12" y1="16" x2="12" y2="8"/></svg>',
    Move: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>',
    Settings: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
    FileText: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
  }
  return icons[name] || ''
}
</script>

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
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s;
  position: relative;
  margin: 0 8px;
  border-radius: var(--radius-sm);
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
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.nav-item :deep(svg) {
  display: block;
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
