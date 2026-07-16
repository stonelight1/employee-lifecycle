import { get, post } from '@/api'
import type { WorkItem, WorkItemsResponse } from '@/types/work-item'
import dayjs from 'dayjs'

/**
 * 获取工作事项（优先使用后端聚合接口）
 */
export async function fetchWorkItems(params?: {
  keyword?: string
  type?: string
  department?: string
  priority?: string
}): Promise<WorkItem[]> {
  // 尝试后端聚合接口
  try {
    const res = await get<WorkItemsResponse>('/work-items', {
      keyword: params?.keyword,
      source_type: params?.type,
    })
    if (res.success && res.data?.items) {
      return res.data.items.map(normalizeWorkItem)
    }
    throw new Error('工作事项聚合接口响应结构错误')
  } catch (e: any) {
    if (e?.status !== 404 && e?.response?.status !== 404) {
      throw e
    }
    console.warn('work-items aggregate endpoint unavailable, fallback enabled')
  }

  // TODO: 旧后端兼容路径。删除条件：所有部署环境均提供 /work-items 聚合接口后移除。
  const [taskRes, todoRes] = await Promise.all([
    get<{ items: any[]; total: number }>('/followup-tasks', { page: 1, page_size: 200 }),
    get<{ items: any[]; total: number }>('/todos', { page: 1, page_size: 200 }),
  ])

  const items: WorkItem[] = []

  // Convert followup tasks
  ;(taskRes.data?.items || []).forEach((t: any) => {
    const dueDate = t.planned_date ? dayjs(t.planned_date) : null
    const today = dayjs().startOf('day')
    let overdueDays = 0
    let daysUntilDue: number | null = null
    if (dueDate) {
      daysUntilDue = dueDate.diff(today, 'day')
      overdueDays = daysUntilDue < 0 ? Math.abs(daysUntilDue) : 0
    }
    items.push({
      id: `FOLLOWUP_TASK_${t.id}`,
      source_type: 'FOLLOWUP_TASK',
      source_id: t.id,
      title: t.task_name,
      due_at: t.planned_date,
      status: t.followup_status,
      risk_level: 'NONE',
      overdue_days: overdueDays,
      days_until_due: daysUntilDue,
    })
  })

  // Convert todos
  ;(todoRes.data?.items || []).forEach((t: any) => {
    const dueDate = t.due_at ? dayjs(t.due_at) : null
    const today = dayjs().startOf('day')
    let overdueDays = 0
    let daysUntilDue: number | null = null
    if (dueDate) {
      daysUntilDue = dueDate.diff(today, 'day')
      overdueDays = daysUntilDue < 0 ? Math.abs(daysUntilDue) : 0
    }
    items.push({
      id: `TODO_${t.id}`,
      source_type: 'TODO',
      source_id: t.id,
      title: t.title,
      due_at: t.due_at,
      status: t.todo_status === 'COMPLETED' ? 'COMPLETED' : t.todo_status === 'CANCELLED' ? 'CANCELLED' : 'PENDING',
      risk_level: 'NONE',
      overdue_days: overdueDays,
      days_until_due: daysUntilDue,
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

  return filtered
}

function normalizeWorkItem(raw: any): WorkItem {
  const dueDate = raw.due_at ? dayjs(raw.due_at) : null
  const today = dayjs().startOf('day')
  let overdueDays = 0
  let daysUntilDue: number | null = null
  if (dueDate) {
    daysUntilDue = dueDate.diff(today, 'day')
    overdueDays = daysUntilDue < 0 ? Math.abs(daysUntilDue) : 0
  }
  return {
    id: raw.id,
    source_type: raw.source_type,
    source_id: raw.source_id,
    employee_id: raw.employee_id,
    employee_name: raw.employee_name || '',
    department: raw.department || '',
    position: raw.position || '',
    title: raw.title,
    due_at: raw.due_at,
    status: raw.status,
    risk_level: raw.risk_level || 'NONE',
    overdue_days: overdueDays,
    days_until_due: daysUntilDue,
  }
}

/**
 * 完成工作事项（待办完成或跟进任务提交确认）
 */
export async function completeWorkItem(item: WorkItem): Promise<void> {
  if (item.source_type === 'TODO') {
    await post(`/todos/${item.source_id}/complete`, { remark: null })
  } else {
    // 跟进任务：根据当前状态决定调用哪个接口
    await post(`/followup-tasks/${item.source_id}/submit`)
  }
}

/**
 * 开始处理跟进任务
 */
export async function startFollowupTask(taskId: number): Promise<void> {
  await post(`/followup-tasks/${taskId}/start`)
}

/**
 * 跟进任务提交确认
 */
export async function submitFollowupTask(taskId: number): Promise<void> {
  await post(`/followup-tasks/${taskId}/submit`)
}

/**
 * 跟进任务确认完成
 */
export async function confirmFollowupTask(taskId: number): Promise<void> {
  await post(`/followup-tasks/${taskId}/confirm`, { comment: null })
}

/**
 * 跟进任务驳回
 */
export async function rejectFollowupTask(taskId: number): Promise<void> {
  await post(`/followup-tasks/${taskId}/reject`, { comment: '请补充沟通记录' })
}

/**
 * 获取跟进任务详情
 */
export async function getFollowupTask(taskId: number): Promise<any> {
  const res = await get<any>(`/followup-tasks/${taskId}`)
  return res.data
}
