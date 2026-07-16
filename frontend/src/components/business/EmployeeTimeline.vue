<script setup lang="ts">
import { formatDate } from '@/utils/date'

interface TimelineEvent {
  date: string
  title: string
  description?: string
  type?: 'system' | 'followup' | 'communication' | 'risk' | 'probation' | 'regularization' | 'change' | 'separation'
}

withDefaults(defineProps<{
  events?: TimelineEvent[]
  maxItems?: number
}>(), {
  events: () => [],
  maxItems: 10,
})
</script>

<template>
  <div class="timeline">
    <div v-if="events.length === 0" class="timeline-empty">
      <p>暂无时间线记录</p>
    </div>
    <div v-else class="timeline-list">
      <div v-for="(event, idx) in events.slice(0, maxItems)" :key="idx" class="timeline-item">
        <div class="timeline-dot" :class="`dot-${event.type || 'system'}`" />
        <div class="timeline-content">
          <div class="timeline-date">{{ formatDate(event.date) }}</div>
          <div class="timeline-title">{{ event.title }}</div>
          <p v-if="event.description" class="timeline-desc">{{ event.description }}</p>
        </div>
      </div>
      <div v-if="events.length > maxItems" class="timeline-more">
        <button class="more-btn">展开全部 ({{ events.length - maxItems }} 条)</button>
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
.timeline-list {
  position: relative;
  padding-left: 20px;
}
.timeline-list::before {
  content: '';
  position: absolute;
  left: 7px;
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
.timeline-dot {
  position: absolute;
  left: -16px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-border);
  border: 2px solid var(--color-surface);
  z-index: 1;
}
.dot-system { background: var(--color-text-tertiary); }
.dot-followup { background: var(--color-primary); }
.dot-communication { background: var(--color-teal); }
.dot-risk { background: var(--color-warning); }
.dot-probation { background: var(--color-primary); }
.dot-regularization { background: var(--color-success); }
.dot-change { background: #7C3AED; }
.dot-separation { background: var(--color-danger); }

.timeline-content {
  min-width: 0;
}
.timeline-date {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-bottom: 2px;
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
