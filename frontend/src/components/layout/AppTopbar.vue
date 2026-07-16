<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Plus } from 'lucide-vue-next'

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

// ====== 员工中心页面的生命周期筛选 ======
const isEmployeePage = computed(() => route.path === '/employees')

const currentStage = computed(() => (route.query.lifecycle_stage as string) || '')

const stageFilters = [
  { label: '全部', value: '' },
  { label: '待入职', value: 'PENDING' },
  { label: '试用期', value: 'PROBATION' },
  { label: '待转正', value: 'REGULARIZATION_PENDING' },
  { label: '正式在职', value: 'ACTIVE' },
  { label: '离职办理中', value: 'SEPARATING' },
  { label: '已离职', value: 'SEPARATED' },
]

function setStageFilter(value: string) {
  router.replace({
    query: {
      ...route.query,
      lifecycle_stage: value || undefined,
      page: undefined,
    },
  })
}

// ====== 员工中心页面的搜索 ======
const employeeSearchQuery = ref('')

// 从路由同步搜索关键词
watch(() => route.query.keyword, (kw) => {
  if (isEmployeePage.value) {
    employeeSearchQuery.value = (kw as string) || ''
  }
})

let searchTimer: ReturnType<typeof setTimeout> | null = null
function onEmployeeSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    const val = employeeSearchQuery.value.trim()
    router.replace({
      query: {
        ...route.query,
        keyword: val || undefined,
        page: undefined,
      },
    })
  }, 300)
}

// ====== 全局搜索 ======
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

      <!-- 员工中心页面的生命周期筛选 -->
      <div v-if="isEmployeePage" class="stage-filters">
        <button
          v-for="f in stageFilters"
          :key="f.value"
          class="stage-filter-btn"
          :class="{ active: currentStage === f.value }"
          @click="setStageFilter(f.value)"
        >
          {{ f.label }}
        </button>
      </div>
    </div>

    <div class="topbar-right">
      <!-- 员工中心页面的实时搜索 -->
      <div v-if="isEmployeePage" class="search-wrapper employee-search">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          v-model="employeeSearchQuery"
          class="search-input"
          placeholder="搜索姓名、编号、手机号、部门或岗位"
          @input="onEmployeeSearchInput"
        />
      </div>

      <!-- 非员工中心页面的全局搜索 -->
      <div v-else class="search-wrapper" :class="{ expanded: showSearch }">
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

      <button class="btn-add" @click="goToNewEmployee">
        <Plus :size="16" />
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
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}
.topbar-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

/* ===== 生命周期筛选标签（员工中心页） ===== */
.stage-filters {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  overflow-x: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.stage-filters::-webkit-scrollbar {
  display: none;
}
.stage-filter-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border);
  border-radius: 99px;
  background: var(--color-surface);
  font-size: var(--font-size-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--color-text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.stage-filter-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.stage-filter-btn.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

/* ===== 搜索 ===== */
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.search-wrapper {
  position: relative;
  max-width: 400px;
  width: 100%;
}
.search-wrapper.employee-search {
  max-width: 280px;
  width: 280px;
}
.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-tertiary);
  pointer-events: none;
  z-index: 1;
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
