<script setup lang="ts">
import EmployeeAvatar from './EmployeeAvatar.vue'
import LifecycleBadge from './LifecycleBadge.vue'
import RiskBadge from './RiskBadge.vue'

interface EmployeeIdentity {
  name?: string
  department?: string
  position?: string
  hireDate?: string
  status?: string
  riskLevel?: string
  nextAction?: string
}

withDefaults(defineProps<{
  employee?: EmployeeIdentity
}>(), {})
</script>

<template>
  <div class="identity-bar">
    <EmployeeAvatar :name="employee?.name" size="lg" />
    <div class="identity-info">
      <div class="identity-name-row">
        <h3 class="identity-name">{{ employee?.name || '—' }}</h3>
        <LifecycleBadge :status="employee?.status" size="sm" />
        <RiskBadge :level="employee?.riskLevel" size="sm" />
      </div>
      <div class="identity-meta">
        <span v-if="employee?.department">{{ employee.department }}</span>
        <template v-if="employee?.department && employee?.position">
          <span class="dot">·</span>
        </template>
        <span v-if="employee?.position">{{ employee.position }}</span>
        <template v-if="employee?.hireDate">
          <span class="dot">·</span>
          <span>{{ employee.hireDate }} 入职</span>
        </template>
      </div>
      <div v-if="employee?.nextAction" class="identity-next">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
        {{ employee.nextAction }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.identity-bar {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.identity-info {
  flex: 1;
  min-width: 0;
}
.identity-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.identity-name {
  font-size: var(--font-size-lg);
  font-weight: 600;
}
.identity-meta {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.dot {
  color: var(--color-text-tertiary);
  margin: 0 2px;
}
.identity-next {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  margin-top: 6px;
}
</style>
