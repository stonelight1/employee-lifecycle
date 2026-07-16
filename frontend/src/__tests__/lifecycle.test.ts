/**
 * 生命周期判断测试
 *
 * 规则（与后端 resolve_lifecycle_stage 一致）：
 * - 没有当前任职 → UNKNOWN
 * - employment_status = PENDING → PENDING
 * - employment_status = SEPARATING → SEPARATING
 * - employment_status = SEPARATED → SEPARATED
 * - employment_status = ACTIVE:
 *   - probation_status = NOT_STARTED / IN_PROGRESS → PROBATION
 *   - probation_status = PENDING_REVIEW → REGULARIZATION_PENDING
 *   - probation_status = REGULARIZED / FAILED / TERMINATED → ACTIVE
 */
import { describe, it, expect } from 'vitest'
import { resolveLifecycleStage, isInProbation, pickCurrentEmployment } from '@/utils/lifecycle'
import type { EmploymentItem } from '@/types'

// Helper to create a minimal employment object
function makeEmployment(overrides: Partial<EmploymentItem> = {}): EmploymentItem {
  return {
    id: 1,
    employee_id: 1,
    employment_seq: 1,
    employment_status: 'ACTIVE',
    hire_date: '2026-01-01',
    probation_status: 'NOT_STARTED',
    ...overrides,
  }
}

describe('resolveLifecycleStage', () => {
  it('无当前任职 → UNKNOWN', () => {
    expect(resolveLifecycleStage(null)).toBe('UNKNOWN')
    expect(resolveLifecycleStage(undefined)).toBe('UNKNOWN')
  })

  it('PENDING → PENDING', () => {
    const emp = makeEmployment({ employment_status: 'PENDING' })
    expect(resolveLifecycleStage(emp)).toBe('PENDING')
  })

  it('ACTIVE + NOT_STARTED → PROBATION', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'NOT_STARTED',
    })
    expect(resolveLifecycleStage(emp)).toBe('PROBATION')
  })

  it('ACTIVE + IN_PROGRESS → PROBATION', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'IN_PROGRESS',
    })
    expect(resolveLifecycleStage(emp)).toBe('PROBATION')
  })

  it('ACTIVE + PENDING_REVIEW → REGULARIZATION_PENDING', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'PENDING_REVIEW',
    })
    expect(resolveLifecycleStage(emp)).toBe('REGULARIZATION_PENDING')
  })

  it('ACTIVE + REGULARIZED → ACTIVE', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'REGULARIZED',
    })
    expect(resolveLifecycleStage(emp)).toBe('ACTIVE')
  })

  it('ACTIVE + FAILED → ACTIVE', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'FAILED',
    })
    expect(resolveLifecycleStage(emp)).toBe('ACTIVE')
  })

  it('ACTIVE + TERMINATED → ACTIVE', () => {
    const emp = makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'TERMINATED',
    })
    expect(resolveLifecycleStage(emp)).toBe('ACTIVE')
  })

  it('SEPARATING → SEPARATING', () => {
    const emp = makeEmployment({ employment_status: 'SEPARATING' })
    expect(resolveLifecycleStage(emp)).toBe('SEPARATING')
  })

  it('SEPARATED → SEPARATED', () => {
    const emp = makeEmployment({ employment_status: 'SEPARATED' })
    expect(resolveLifecycleStage(emp)).toBe('SEPARATED')
  })
})

describe('isInProbation', () => {
  it('PROBATION 状态返回 true', () => {
    expect(isInProbation(makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'IN_PROGRESS',
    }))).toBe(true)
  })

  it('ACTIVE 状态返回 false', () => {
    expect(isInProbation(makeEmployment({
      employment_status: 'ACTIVE',
      probation_status: 'REGULARIZED',
    }))).toBe(false)
  })

  it('null 返回 false', () => {
    expect(isInProbation(null)).toBe(false)
  })
})

describe('pickCurrentEmployment', () => {
  it('空数组返回 null', () => {
    expect(pickCurrentEmployment([])).toBeNull()
  })

  it('null/undefined 返回 null', () => {
    expect(pickCurrentEmployment(null)).toBeNull()
    expect(pickCurrentEmployment(undefined)).toBeNull()
  })

  it('从多个有效任职中选出最新的一条', () => {
    const emp1 = makeEmployment({ id: 1, employment_seq: 1, employment_status: 'ACTIVE' })
    const emp2 = makeEmployment({ id: 2, employment_seq: 2, employment_status: 'ACTIVE' })
    expect(pickCurrentEmployment([emp1, emp2])?.id).toBe(2)
  })

  it('优先选择 PENDING/ACTIVE/SEPARATING 状态的任职', () => {
    const sep = makeEmployment({ id: 1, employment_seq: 2, employment_status: 'SEPARATED' })
    const active = makeEmployment({ id: 2, employment_seq: 1, employment_status: 'ACTIVE' })
    // 虽然 sep 的 seq 更大，但 active 状态优先
    expect(pickCurrentEmployment([sep, active])?.id).toBe(2)
  })
})
