import type { EmploymentItem } from '@/types'

/**
 * 生命周期阶段类型
 * 与后端 enums 和 resolve_lifecycle_stage() 严格一致
 */
export type LifecycleStage =
  | 'PENDING'              // 待入职
  | 'PROBATION'            // 试用期（probation_status = NOT_STARTED / IN_PROGRESS）
  | 'REGULARIZATION_PENDING' // 待转正（probation_status = PENDING_REVIEW）
  | 'ACTIVE'               // 正式在职（probation_status = REGULARIZED/FAILED/TERMINATED）
  | 'SEPARATING'           // 离职中
  | 'SEPARATED'            // 已离职
  | 'UNKNOWN'              // 无当前任职

/**
 * 生命周期阶段的中文标签与颜色
 */
export const lifecycleStageInfo: Record<string, { label: string; color: string; background: string }> = {
  PENDING: { label: '待入职', color: '#7C3AED', background: '#F3E8FF' },
  PROBATION: { label: '试用期', color: '#2563EB', background: '#EFF6FF' },
  REGULARIZATION_PENDING: { label: '待转正', color: '#D97706', background: '#FFF7E8' },
  ACTIVE: { label: '正式在职', color: '#16825D', background: '#EAF8F1' },
  SEPARATING: { label: '离职中', color: '#E11D48', background: '#FFF1F2' },
  SEPARATED: { label: '已离职', color: '#667085', background: '#F2F4F7' },
  UNKNOWN: { label: '未知', color: '#98A2B3', background: '#F2F4F7' },
}

/**
 * 统一生命周期阶段判断
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
 *
 * @param employment 当前有效任职（可为 null）
 * @param fallbackStatus 无任职时的备用值
 */
export function resolveLifecycleStage(
  employment: EmploymentItem | null | undefined,
  fallbackStatus?: string,
): LifecycleStage {
  if (!employment) return (fallbackStatus as LifecycleStage) || 'UNKNOWN'

  const es = employment.employment_status
  if (es === 'PENDING') return 'PENDING'
  if (es === 'SEPARATING') return 'SEPARATING'
  if (es === 'SEPARATED') return 'SEPARATED'

  // es === 'ACTIVE'
  const ps = employment.probation_status
  if (ps === 'NOT_STARTED' || ps === 'IN_PROGRESS') return 'PROBATION'
  if (ps === 'PENDING_REVIEW') return 'REGULARIZATION_PENDING'
  // REGULARIZED, FAILED, TERMINATED → ACTIVE
  return 'ACTIVE'
}

/**
 * 判断是否在试用期（PROBATION 状态）
 */
export function isInProbation(employment: EmploymentItem | null | undefined): boolean {
  return resolveLifecycleStage(employment) === 'PROBATION'
}

/**
 * 从任职列表中选出当前有效任职
 * 规则：优先 PENDING / ACTIVE / SEPARATING 中的任职，取最新的一条
 */
export function pickCurrentEmployment(
  employments: EmploymentItem[] | null | undefined,
): EmploymentItem | null {
  if (!employments || employments.length === 0) return null
  const active = employments.filter(
    (item) => ['PENDING', 'ACTIVE', 'SEPARATING'].includes(item.employment_status),
  )
  if (active.length > 0) {
    // 按 employment_seq 取最新
    return active.reduce((latest, curr) =>
      curr.employment_seq > latest.employment_seq ? curr : latest,
    )
  }
  // 没有有效在职，取最近的一条
  return employments.reduce((latest, curr) =>
    curr.employment_seq > latest.employment_seq ? curr : latest,
  )
}

export interface FollowupTaskNode {
  task_id: number
  node_name: string
  planned_date: string | null
  status: string
  completed_at: string | null
}

export interface FollowupProgress {
  completed_count: number
  total_count: number
  completed_nodes: { task_id: number; node_name: string; completed_at: string | null }[]
  all_nodes: FollowupTaskNode[]
  next_node: {
    task_id: number | null
    node_name: string | null
    planned_date: string | null
    status: string
    days_until_due: number | null
    overdue_days: number
  }
}

function toDateOnly(value: string | Date): Date {
  const date = value instanceof Date ? value : new Date(value)
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/**
 * 从跟进任务列表计算完成数量、全部节点和下一节点。
 */
export function resolveFollowupProgress(
  tasks: FollowupTaskNode[] | null | undefined,
  today: string | Date = new Date(),
): FollowupProgress {
  const safeTasks = [...(tasks || [])]
  const todayDate = toDateOnly(today)
  const completedNodes = safeTasks
    .filter((task) => task.status === 'COMPLETED')
    .map((task) => ({
      task_id: task.task_id,
      node_name: task.node_name,
      completed_at: task.completed_at,
    }))

  const activeTasks = safeTasks
    .filter((task) => ['PENDING', 'IN_PROGRESS', 'PENDING_CONFIRMATION'].includes(task.status))
    .sort((a, b) => {
      const aTime = a.planned_date ? toDateOnly(a.planned_date).getTime() : Number.POSITIVE_INFINITY
      const bTime = b.planned_date ? toDateOnly(b.planned_date).getTime() : Number.POSITIVE_INFINITY
      if (aTime !== bTime) return aTime - bTime
      return a.task_id - b.task_id
    })

  if (activeTasks.length > 0) {
    const nextTask = activeTasks[0]
    let daysUntilDue: number | null = null
    if (nextTask.planned_date) {
      daysUntilDue = Math.round(
        (toDateOnly(nextTask.planned_date).getTime() - todayDate.getTime()) / 86_400_000,
      )
    }

    return {
      completed_count: completedNodes.length,
      total_count: safeTasks.length,
      completed_nodes: completedNodes,
      all_nodes: safeTasks,
      next_node: {
        task_id: nextTask.task_id,
        node_name: nextTask.node_name,
        planned_date: nextTask.planned_date,
        status: nextTask.status,
        days_until_due: daysUntilDue,
        overdue_days: daysUntilDue !== null && daysUntilDue < 0 ? Math.abs(daysUntilDue) : 0,
      },
    }
  }

  return {
    completed_count: completedNodes.length,
    total_count: safeTasks.length,
    completed_nodes: completedNodes,
    all_nodes: safeTasks,
    next_node: {
      task_id: null,
      node_name: null,
      planned_date: null,
      status: safeTasks.length > 0 && completedNodes.length === safeTasks.length ? 'ALL_COMPLETED' : 'NO_TASKS',
      days_until_due: null,
      overdue_days: 0,
    },
  }
}
