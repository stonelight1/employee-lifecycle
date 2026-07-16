<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const searchQuery = ref('')
const showSearch = ref(false)
let blurTimer: ReturnType<typeof setTimeout> | null = null

const breadcrumb = ref('员工生命周期管理系统')

// 根据路由生成面包屑
const routeTitles: Record<string, string> = {
  Dashboard: '工作台',
  WorkItemCenter: '工作事项',
  EmployeeList: '员工中心',
  EmployeeCreate: '新增员工',
  EmployeeDetail: '员工详情',
  EmployeeEdit: '编辑员工',
  EmploymentCreate: '新增任职',
  EmploymentDetail: '任职详情',
  ProbationCenter: '试用期中心',
  RegularizationCenter: '转正管理',
  MovementCenter: '异动与离职',
  FollowupNodeList: '节点配置',
  FollowupTaskList: '跟进任务',
  FollowupTaskDetail: '任务详情',
  TodoList: '待办事项',
  OperationLogList: '操作日志',
}

function updateBreadcrumb() {
  const name = route.name as string
  breadcrumb.value = routeTitles[name] || '员工生命周期管理系统'
}

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({
      path: '/employees',
      query: { keyword: searchQuery.value.trim() },
    })
    searchQuery.value = ''
    showSearch.value = false
  }
}

function goToNewEmployee() {
  router.push('/employees/new')
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    showSearch.value = !showSearch.value
    if (showSearch.value) {
      setTimeout(() => {
        const input = document.querySelector('.search-input') as HTMLInputElement
        input?.focus()
      }, 100)
    }
  }
}

function onSearchBlur() {
  blurTimer = setTimeout(() => { showSearch.value = false }, 200)
}

function onSearchFocus() {
  if (blurTimer) clearTimeout(blurTimer)
  showSearch.value = true
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  updateBreadcrumb()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <span class="topbar-title">{{ breadcrumb }}</span>
    </div>

    <div class="topbar-center">
      <div class="search-wrapper" :class="{ expanded: showSearch }">
        <form @submit.prevent="handleSearch">
          <input
            v-model="searchQuery"
            class="search-input"
            :class="{ active: showSearch }"
            type="text"
            placeholder="搜索员工姓名  Ctrl+K"
            @focus="onSearchFocus"
            @blur="onSearchBlur"
          />
        </form>
        <button v-if="!showSearch" class="search-trigger" aria-label="搜索" @click="showSearch = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
          </svg>
        </button>
      </div>
    </div>

    <div class="topbar-right">
      <button class="btn-add" @click="goToNewEmployee">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span>新增员工</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  gap: 16px;
  flex-shrink: 0;
}
.topbar-left {
  min-width: 0;
}
.topbar-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.topbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
}
.search-wrapper {
  position: relative;
  max-width: 400px;
  width: 100%;
}
.search-input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  background: var(--color-bg);
  outline: none;
  transition: all 0.2s;
}
.search-input:focus {
  border-color: var(--color-primary);
  background: var(--color-surface);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}
.search-input::placeholder {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}
.search-trigger {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-tertiary);
  padding: 2px;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.btn-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-add:hover {
  background: var(--color-primary-hover);
}
</style>
