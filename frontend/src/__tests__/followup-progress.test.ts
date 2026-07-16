/**
 * 跟进节点进度计算测试
 *
 * 提取纯函数 resolveFollowupProgress(tasks, today) 用于测试。
 * 覆盖场景：
 *   - 所有任务未开始
 *   - 部分任务完成
 *   - 存在一个逾期任务
 *   - 存在多个逾期任务
 *   - 存在待确认任务
 *   - 所有任务完成
 *   - 所有任务取消
 *   - 没有任务
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import { resolveFollowupProgress, type FollowupTaskNode } from '@/utils/lifecycle'

// 固定当前时间：2026-07-16 10:00 CST (UTC+8)
const FIXED_NOW = new Date('2026-07-16T10:00:00+08:00')

beforeAll(() => {
  vi.useFakeTimers()
  vi.setSystemTime(FIXED_NOW)
})

afterAll(() => {
  vi.useRealTimers()
})

describe('resolveFollowupProgress', () => {
  it('所有任务未开始 → 下一节点为最早计划日', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'PENDING', completed_at: null },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'PENDING', completed_at: null },
      { task_id: 3, node_name: '30天跟进', planned_date: '2026-07-31', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.total_count).toBe(3)
    expect(result.completed_count).toBe(0)
    expect(result.next_node?.task_id).toBe(1)
    expect(result.next_node?.node_name).toBe('7天跟进')
  })

  it('部分任务完成 → 下一节点是第一个未完成的', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'COMPLETED', completed_at: '2026-07-08T10:00:00' },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'PENDING', completed_at: null },
      { task_id: 3, node_name: '30天跟进', planned_date: '2026-07-31', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.completed_count).toBe(1)
    expect(result.next_node?.task_id).toBe(2)
    expect(result.next_node?.node_name).toBe('15天跟进')
  })

  it('存在逾期任务 → 下一节点显示逾期天数', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'PENDING', completed_at: null },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks, '2026-07-16')
    expect(result.next_node?.task_id).toBe(1)
    expect(result.next_node?.overdue_days).toBe(8)
    expect(result.next_node?.days_until_due).toBe(-8)
  })

  it('存在多个逾期 → 选择最早逾期的', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'PENDING', completed_at: null },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-10', status: 'PENDING', completed_at: null },
      { task_id: 3, node_name: '30天跟进', planned_date: '2026-07-31', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks, '2026-07-16')
    expect(result.next_node?.task_id).toBe(1)
    expect(result.next_node?.node_name).toBe('7天跟进')
  })

  it('存在待确认任务 → 优先级：待确认也是未完成', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'COMPLETED', completed_at: '2026-07-08T10:00:00' },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'PENDING_CONFIRMATION', completed_at: null },
      { task_id: 3, node_name: '30天跟进', planned_date: '2026-07-31', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.next_node?.task_id).toBe(2)
    expect(result.next_node?.status).toBe('PENDING_CONFIRMATION')
  })

  it('所有任务完成 → ALL_COMPLETED', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'COMPLETED', completed_at: '2026-07-08T10:00:00' },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'COMPLETED', completed_at: '2026-07-16T10:00:00' },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.completed_count).toBe(2)
    expect(result.next_node?.status).toBe('ALL_COMPLETED')
  })

  it('所有任务取消 → NO_TASKS（取消不算完成）', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'CANCELLED', completed_at: null },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'CANCELLED', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.completed_count).toBe(0)
    expect(result.total_count).toBe(2)
    expect(result.next_node?.status).toBe('NO_TASKS')
  })

  it('没有任务 → NO_TASKS', () => {
    const tasks: FollowupTaskNode[] = []
    const result = resolveFollowupProgress(tasks)
    expect(result.total_count).toBe(0)
    expect(result.completed_count).toBe(0)
    expect(result.next_node?.status).toBe('NO_TASKS')
  })

  it('取消+完成混合 → 已完成计入完成，取消的不计入', () => {
    const tasks: FollowupTaskNode[] = [
      { task_id: 1, node_name: '7天跟进', planned_date: '2026-07-08', status: 'COMPLETED', completed_at: '2026-07-08T10:00:00' },
      { task_id: 2, node_name: '15天跟进', planned_date: '2026-07-16', status: 'CANCELLED', completed_at: null },
      { task_id: 3, node_name: '30天跟进', planned_date: '2026-07-31', status: 'PENDING', completed_at: null },
    ]
    const result = resolveFollowupProgress(tasks)
    expect(result.completed_count).toBe(1)
    expect(result.total_count).toBe(3)
    expect(result.next_node?.task_id).toBe(3)
  })
})
