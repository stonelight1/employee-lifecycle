import { get } from '@/api'

export interface DashboardMetrics {
  active_employee_count: number
  probation_employee_count: number
  regularization_due_7d_count: number
  overdue_work_item_count: number
}

export interface LifecycleDistribution {
  stage: string
  count: number
}

export interface PriorityWorkItem {
  id: string
  employee_name: string
  department?: string
  position?: string
  title: string
  due_at?: string
  overdue_days: number
  risk_level?: string
  source_type: string
  source_id: number
}

export interface UpcomingEvent {
  date: string
  title: string
  employee_name?: string
  type: string
}

export interface RiskEmployee {
  name: string
  department?: string
  position?: string
  risk_level: string
  risk_reason?: string
  last_communication_date?: string
}

export interface DashboardData {
  metrics: DashboardMetrics
  lifecycle_distribution: LifecycleDistribution[]
  priority_work_items: PriorityWorkItem[]
  upcoming_events: UpcomingEvent[]
  risk_employees: RiskEmployee[]
}

/**
 * 检查 API 连接是否正常
 */
async function checkApiConnection(): Promise<boolean> {
  try {
    const res = await get<any>('/health')
    return res.success === true
  } catch {
    return false
  }
}

export async function fetchDashboard(): Promise<DashboardData> {
  // 如果后端不运行，直接返回空数据，不崩溃
  const connected = await checkApiConnection()
  if (!connected) {
    console.warn('[Dashboard] 后端 API 未连接，返回空数据')
    return createEmptyDashboardData()
  }

  // 尝试后端聚合接口
  try {
    const res = await get<DashboardData>('/dashboard/overview')
    if (res.success && res.data) return res.data
  } catch {
    // 后端无聚合接口，走客户端聚合
  }

  // 客户端聚合（N+1 查询）
  try {
    return await aggregateFromClient()
  } catch (e) {
    console.warn('[Dashboard] 客户端聚合失败:', e)
    return createEmptyDashboardData()
  }
}

async function aggregateFromClient(): Promise<DashboardData> {
  const [empRes, taskRes, todoRes] = await Promise.all([
    get<{ items: any[]; total: number }>('/employees', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/followup-tasks', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/todos', { page: 1, page_size: 200 }),
  ])

  const employees = empRes.data?.items || []
  const tasks = taskRes.data?.items || []
  const todos = todoRes.data?.items || []

  // 获取每个员工的当前任职信息
  const currentEmployments: any[] = []
  await Promise.all(
    employees.map(async (employee: any) => {
      try {
        const res = await get<{ items: any[]; total: number }>(`/employees/${employee.id}/employments`)
        const items = res.data?.items || []
        const current = items.find(
          (item: any) => ['PENDING', 'ACTIVE', 'SEPARATING'].includes(item.employment_status),
        ) || items[0]
        if (current) {
          currentEmployments.push({
            ...current,
            employee_name: employee.name,
            employee_id: employee.id,
          })
        }
      } catch {
        // 跳过无任职的员工
      }
    }),
  )

  // 统计生命周期分布
  const probationCount = currentEmployments.filter((e: any) =>
    e.employment_status === 'ACTIVE' &&
    ['NOT_STARTED', 'IN_PROGRESS', 'PENDING_REVIEW'].includes(e.probation_status),
  ).length
  const activeCount = currentEmployments.filter((e: any) =>
    e.employment_status === 'ACTIVE' &&
    !['NOT_STARTED', 'IN_PROGRESS', 'PENDING_REVIEW'].includes(e.probation_status),
  ).length
  const pendingCount = currentEmployments.filter((e: any) => e.employment_status === 'PENDING').length
  const separatingCount = currentEmployments.filter((e: any) => e.employment_status === 'SEPARATING').length
  const separatedCount = currentEmployments.filter((e: any) => e.employment_status === 'SEPARATED').length

  // 统计逾期事项
  const now = new Date()
  const overdueTasks = tasks.filter((t: any) =>
    ['PENDING', 'IN_PROGRESS'].includes(t.followup_status) &&
    t.planned_date && new Date(t.planned_date) < now,
  )
  const overdueTodos = todos.filter((t: any) =>
    t.todo_status === 'PENDING' &&
    t.due_at && new Date(t.due_at) < now,
  )

  // 构建优先级事项
  const priorityWorkItems: PriorityWorkItem[] = [
    ...overdueTasks.map((t: any) => ({
      id: `task-${t.id}`,
      source_type: 'FOLLOWUP_TASK' as const,
      source_id: t.id,
      title: t.task_name,
      due_at: t.planned_date,
      overdue_days: Math.round((now.getTime() - new Date(t.planned_date).getTime()) / (1000 * 60 * 60 * 24)),
      risk_level: 'NONE',
      employee_name: '',
    })),
    ...overdueTodos.map((t: any) => ({
      id: `todo-${t.id}`,
      source_type: 'TODO' as const,
      source_id: t.id,
      title: t.title,
      due_at: t.due_at,
      overdue_days: t.due_at ? Math.round((now.getTime() - new Date(t.due_at).getTime()) / (1000 * 60 * 60 * 24)) : 0,
      risk_level: 'NONE',
      employee_name: '',
    })),
  ].slice(0, 8)

  // 近期转正
  let regularizationDue7d = 0
  const nowDate = now.toISOString().slice(0, 10)
  const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  for (const emp of currentEmployments) {
    if (emp.probation_end_date && emp.probation_end_date >= nowDate && emp.probation_end_date <= nextWeek) {
      regularizationDue7d++
    }
  }

  return {
    metrics: {
      active_employee_count: activeCount + probationCount,
      probation_employee_count: probationCount,
      regularization_due_7d_count: regularizationDue7d,
      overdue_work_item_count: overdueTasks.length + overdueTodos.length,
    },
    lifecycle_distribution: [
      { stage: 'PENDING', count: pendingCount },
      { stage: 'PROBATION', count: probationCount },
      { stage: 'ACTIVE', count: activeCount },
      { stage: 'SEPARATING', count: separatingCount },
      { stage: 'SEPARATED', count: separatedCount },
    ],
    priority_work_items: priorityWorkItems,
    upcoming_events: [],
    risk_employees: [],
  }
}

function createEmptyDashboardData(): DashboardData {
  return {
    metrics: {
      active_employee_count: 0,
      probation_employee_count: 0,
      regularization_due_7d_count: 0,
      overdue_work_item_count: 0,
    },
    lifecycle_distribution: [],
    priority_work_items: [],
    upcoming_events: [],
    risk_employees: [],
  }
}
