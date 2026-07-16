import { get, post } from '@/api'

export interface WorkItem {
  id: string
  source_type: 'FOLLOWUP_TASK' | 'TODO'
  source_id: number
  employee_id?: number
  employee_name?: string
  department?: string
  position?: string
  title: string
  due_at?: string
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'
  priority: 'HIGH' | 'NORMAL' | 'LOW'
  risk_level?: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
  overdue_days: number
}

export async function fetchWorkItems(params?: {
  keyword?: string
  type?: string
  department?: string
  priority?: string
}): Promise<WorkItem[]> {
  const [taskRes, todoRes] = await Promise.all([
    get<{ items: any[]; total: number }>('/followup-tasks', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/todos', { page: 1, page_size: 200 }),
  ])

  const now = new Date()
  const items: WorkItem[] = []

  // Convert followup tasks
  ;(taskRes.data?.items || []).forEach((t: any) => {
    const dueDate = t.planned_date ? new Date(t.planned_date) : null
    const overdue = dueDate && dueDate < now ? Math.round((now.getTime() - dueDate.getTime()) / (1000 * 60 * 60 * 24)) : 0
    items.push({
      id: `task-${t.id}`,
      source_type: 'FOLLOWUP_TASK',
      source_id: t.id,
      title: t.task_name,
      due_at: t.planned_date,
      status: t.followup_status === 'COMPLETED' ? 'COMPLETED' : t.followup_status === 'CANCELLED' ? 'CANCELLED' : t.followup_status === 'IN_PROGRESS' ? 'IN_PROGRESS' : 'PENDING',
      priority: 'NORMAL',
      risk_level: 'NONE',
      overdue_days: overdue,
    })
  })

  // Convert todos
  ;(todoRes.data?.items || []).forEach((t: any) => {
    const dueDate = t.due_at ? new Date(t.due_at) : null
    const overdue = dueDate && dueDate < now ? Math.round((now.getTime() - dueDate.getTime()) / (1000 * 60 * 60 * 24)) : 0
    items.push({
      id: `todo-${t.id}`,
      source_type: 'TODO',
      source_id: t.id,
      title: t.title,
      due_at: t.due_at,
      status: t.todo_status === 'COMPLETED' ? 'COMPLETED' : 'PENDING',
      priority: t.priority === 'HIGH' ? 'HIGH' : t.priority === 'LOW' ? 'LOW' : 'NORMAL',
      overdue_days: overdue,
    })
  })

  // Apply filters
  let filtered = items
  if (params?.keyword) {
    const kw = params.keyword.toLowerCase()
    filtered = filtered.filter((i) => i.title.toLowerCase().includes(kw) || i.employee_name?.toLowerCase().includes(kw))
  }
  if (params?.type === 'FOLLOWUP_TASK') filtered = filtered.filter((i) => i.source_type === 'FOLLOWUP_TASK')
  if (params?.type === 'TODO') filtered = filtered.filter((i) => i.source_type === 'TODO')
  if (params?.priority) filtered = filtered.filter((i) => i.priority === params.priority)

  return filtered
}

export async function completeWorkItem(item: WorkItem): Promise<void> {
  if (item.source_type === 'TODO') {
    await post(`/todos/${item.source_id}/complete`)
  } else {
    await post(`/followup-tasks/${item.source_id}/submit`)
  }
}
