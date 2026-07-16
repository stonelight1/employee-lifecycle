// 工作事项DTO

export interface WorkItem {
  id: string
  source_type: 'FOLLOWUP_TASK' | 'TODO'
  source_id: number
  employee_id?: number | null
  employee_name?: string
  department?: string
  position?: string
  title: string
  due_at?: string | null
  status: 'PENDING' | 'IN_PROGRESS' | 'PENDING_CONFIRMATION' | 'COMPLETED' | 'CANCELLED'
  risk_level?: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE'
  /** 逾期天数（始终为正数） */
  overdue_days: number
  /** 未来天数（0=今天，负数=已逾期） */
  days_until_due: number | null
}

export interface WorkItemsResponse {
  items: WorkItem[]
  total: number
}
