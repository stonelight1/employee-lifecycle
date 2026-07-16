import { get } from '@/api'
import type { DashboardOverview } from '@/types/dashboard'
import type { ApiResponse, PaginatedData } from '@/types/common'

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

/**
 * 获取工作台概览（优先使用后端聚合接口，失败时降级本地聚合）
 */
export async function fetchDashboard(): Promise<DashboardOverview> {
  const connected = await checkApiConnection()
  if (!connected) {
    console.warn('[Dashboard] 后端 API 未连接，返回空数据')
    return createEmptyDashboardData()
  }

  // 尝试后端聚合接口
  try {
    const res = await get<DashboardOverview>('/dashboard/overview')
    if (res.success && res.data) return res.data
    throw new Error('工作台聚合接口响应结构错误')
  } catch (e: any) {
    // 聚合接口 404 时使用旧接口降级
    if (e?.status === 404 || e?.response?.status === 404) {
      console.warn('dashboard aggregate endpoint unavailable, fallback enabled')
      return await aggregateFromClient()
    }
    // 非 404 错误（500/超时/网络错误）抛出明确错误
    throw e
  }
}

async function aggregateFromClient(): Promise<DashboardOverview> {
  const [empRes, taskRes, todoRes] = await Promise.all([
    get<{ items: any[]; total: number }>('/employees', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/followup-tasks', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/todos', { page: 1, page_size: 200 }),
  ])

  const employees = empRes.data?.items || []
  const tasks = taskRes.data?.items || []
  const todos = todoRes.data?.items || []

  // 获取每个员工的当前任职信息（降级模式下 N+1 不可避免）
  const currentEmployments: any[] = []
  await Promise.all(
    employees.map(async (employee: any) => {
      try {
        const { data: res } = await get<{ items: any[] }>(`/employees/${employee.id}/employments`)
        const items = res?.items || []
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

  const now = new Date()
  const overdueTasks = tasks.filter((t: any) =>
    ['PENDING', 'IN_PROGRESS'].includes(t.followup_status) &&
    t.planned_date && new Date(t.planned_date) < now,
  )
  const overdueTodos = todos.filter((t: any) =>
    t.todo_status === 'PENDING' &&
    t.due_at && new Date(t.due_at) < now,
  )

  const nowDate = now.toISOString().slice(0, 10)
  const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  let regularizationDue7d = 0
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
    ].filter(d => d.count > 0),
    priority_work_items: [
      ...overdueTasks.map((t: any) => ({
        id: `FOLLOWUP_TASK_${t.id}`,
        source_type: 'FOLLOWUP_TASK',
        source_id: t.id,
        employee_name: '',
        department: undefined,
        position: undefined,
        title: t.task_name,
        due_at: t.planned_date,
        overdue_days: Math.max(0, Math.round((now.getTime() - new Date(t.planned_date).getTime()) / (1000 * 60 * 60 * 24))),
        risk_level: 'NONE',
      })),
      ...overdueTodos.map((t: any) => ({
        id: `TODO_${t.id}`,
        source_type: 'TODO',
        source_id: t.id,
        employee_name: '',
        department: undefined,
        position: undefined,
        title: t.title,
        due_at: t.due_at,
        overdue_days: t.due_at ? Math.max(0, Math.round((now.getTime() - new Date(t.due_at).getTime()) / (1000 * 60 * 60 * 24))) : 0,
        risk_level: 'NONE',
      })),
    ].slice(0, 8),
    upcoming_events: [],
    risk_employees: [],
  }
}

function createEmptyDashboardData(): DashboardOverview {
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
