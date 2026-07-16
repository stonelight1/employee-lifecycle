<script setup lang="ts">
import { ref, computed } from 'vue'
import { formatDateTime } from '@/utils/date'
import { getStatusLabel, riskMap } from '@/constants/status'
import {
  UserRound,
  BriefcaseBusiness,
  ClipboardCheck,
  MessageSquareText,
  Sparkles,
  ShieldAlert,
  FileCheck,
  BadgeCheck,
  ArrowLeftRight,
  LogOut,
  Clock,
} from 'lucide-vue-next'

/**
 * 时间线事件类型
 */
interface TimelineEvent {
  id: string
  event_type: string
  event_name: string
  event_time: string
  employee_id: number
  employment_id?: number
  source_id: number
  source_type: string
  title: string
  summary?: string
  operator_name?: string
  metadata?: Record<string, any>
}

const props = withDefaults(defineProps<{
  events?: TimelineEvent[]
  total?: number
  maxItems?: number
  loading?: boolean
  error?: string
}>(), {
  events: () => [],
  total: 0,
  maxItems: 10,
  loading: false,
  error: '',
})

const emit = defineEmits<{
  retry: []
  loadMore: []
}>()

const showAll = ref(false)
const displayEvents = computed(() => {
  if (showAll.value) return props.events
  return props.events.slice(0, props.maxItems)
})
const hasMoreRemote = computed(() => props.total > props.events.length)

/**
 * 根据事件类型返回图标组件
 */
function getEventIcon(type: string) {
  const iconMap: Record<string, any> = {
    EMPLOYEE_CREATED: UserRound,
    EMPLOYMENT_CREATED: BriefcaseBusiness,
    REEMPLOYMENT_CREATED: BriefcaseBusiness,
    EMPLOYMENT_STARTED: BriefcaseBusiness,
    FOLLOWUP_TASK_CREATED: ClipboardCheck,
    FOLLOWUP_TASK_STARTED: ClipboardCheck,
    FOLLOWUP_TASK_SUBMITTED: ClipboardCheck,
    FOLLOWUP_TASK_COMPLETED: ClipboardCheck,
    FOLLOWUP_TASK_CANCELLED: ClipboardCheck,
    COMMUNICATION_CREATED: MessageSquareText,
    AI_SUMMARY_COMPLETED: Sparkles,
    RISK_LEVEL_CHANGED: ShieldAlert,
    PROBATION_REVIEW_CREATED: FileCheck,
    PROBATION_REVIEW_UPDATED: FileCheck,
    REGULARIZATION_STARTED: BadgeCheck,
    REGULARIZATION_COMPLETED: BadgeCheck,
    REGULARIZATION_EXTENDED: Clock,
    EMPLOYMENT_CHANGED: ArrowLeftRight,
    SEPARATION_STARTED: LogOut,
    SEPARATION_COMPLETED: LogOut,
  }
  return iconMap[type] || Clock
}

/**
 * 根据事件类型返回颜色类名
 */
function getDotColor(type: string): string {
  if (type.startsWith('EMPLOYEE') || type.startsWith('EMPLOYMENT')) return 'dot-system'
  if (type.startsWith('FOLLOWUP')) return 'dot-followup'
  if (type.startsWith('COMMUNICATION')) return 'dot-communication'
  if (type.startsWith('AI_SUMMARY')) return 'dot-ai'
  if (type.startsWith('RISK')) return 'dot-risk'
  if (type.startsWith('PROBATION')) return 'dot-probation'
  if (type.startsWith('REGULARIZATION')) return 'dot-regularization'
  if (type.startsWith('EMPLOYMENT_CHANGED')) return 'dot-change'
  if (type.startsWith('SEPARATION')) return 'dot-separation'
  return 'dot-system'
}

/**
 * 获取风险等级中文标签
 */
function getRiskLabel(level?: string): string | null {
  if (!level || level === 'NONE' || level === 'UNSPECIFIED') return null
  const info = riskMap[level]
  return info?.label || level
}

function handleMoreClick() {
  if (hasMoreRemote.value) {
    emit('loadMore')
    return
  }
  showAll.value = true
}
</script>

<template>
  <div class="timeline">
    <!-- Error state -->
    <div v-if="error" class="timeline-error">
      <p>时间线加载失败</p>
      <button class="retry-btn" @click="emit('retry')">重新加载</button>
    </div>

    <!-- Loading state -->
    <div v-else-if="loading" class="timeline-empty">
      <p>加载中...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="events.length === 0" class="timeline-empty">
      <p>暂无时间线记录</p>
    </div>

    <!-- Event list -->
    <div v-else class="timeline-list">
      <div v-for="event in displayEvents" :key="event.id" class="timeline-item">
        <div class="timeline-icon" :class="getDotColor(event.event_type)">
          <component :is="getEventIcon(event.event_type)" :size="14" />
        </div>
        <div class="timeline-content">
          <div class="timeline-header">
            <span class="timeline-time">{{ formatDateTime(event.event_time) }}</span>
            <span v-if="event.operator_name" class="timeline-operator">{{ event.operator_name }}</span>
          </div>
          <div class="timeline-title">{{ event.event_name }}</div>
          <p v-if="event.summary" class="timeline-desc">{{ event.summary }}</p>
          <div v-if="event.metadata?.risk_level" class="timeline-risk">
            <span
              class="risk-tag"
              :class="`risk-${(event.metadata.risk_level || '').toLowerCase()}`"
            >
              风险等级：{{ getRiskLabel(event.metadata.risk_level) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Show more -->
      <div v-if="total > maxItems && (!showAll || hasMoreRemote)" class="timeline-more">
        <button class="more-btn" @click="handleMoreClick">
          {{ hasMoreRemote ? '加载更多' : `展开全部 (${total} 条)` }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  position: relative;
}

.timeline-empty {
  text-align: center;
  padding: 24px;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.timeline-error {
  text-align: center;
  padding: 24px;
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}
.retry-btn {
  margin-top: 8px;
  padding: 4px 12px;
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  font-size: var(--font-size-xs);
  cursor: pointer;
}

.timeline-list {
  position: relative;
  padding-left: 28px;
}
.timeline-list::before {
  content: '';
  position: absolute;
  left: 13px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: var(--color-border);
}

.timeline-item {
  position: relative;
  padding-bottom: 20px;
}
.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-icon {
  position: absolute;
  left: -21px;
  top: 2px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  z-index: 1;
  border: 2px solid var(--color-surface);
}
.dot-system { background: var(--color-text-tertiary); }
.dot-followup { background: var(--color-primary); }
.dot-communication { background: #0D9488; }
.dot-ai { background: #8B5CF6; }
.dot-risk { background: var(--color-warning); }
.dot-probation { background: var(--color-primary); }
.dot-regularization { background: var(--color-success); }
.dot-change { background: #7C3AED; }
.dot-separation { background: var(--color-danger); }

.timeline-content {
  min-width: 0;
}

.timeline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.timeline-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.timeline-operator {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.timeline-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
}

.timeline-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 2px;
  line-height: 1.5;
}

.timeline-risk {
  margin-top: 4px;
}

.risk-tag {
  font-size: var(--font-size-xs);
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
}

.timeline-more {
  padding-top: 8px;
}

.more-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
</style>
