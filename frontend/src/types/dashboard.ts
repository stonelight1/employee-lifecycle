// 工作台概览DTO

export interface DashboardMetrics {
  active_employee_count: number
  probation_employee_count: number
  regularization_due_7d_count: number
  overdue_work_item_count: number
}

export interface DashboardLifecycleDistribution {
  stage: string
  count: number
}

export interface DashboardPriorityWorkItem {
  id: string
  source_type: string
  source_id: number
  employee_name: string
  department?: string
  position?: string
  title: string
  due_at?: string
  overdue_days: number
  risk_level?: string
}

export interface DashboardRiskEmployee {
  name: string
  department?: string
  position?: string
  risk_level: string
  risk_reason?: string
  last_communication_date?: string
}

export interface DashboardOverview {
  metrics: DashboardMetrics
  lifecycle_distribution: DashboardLifecycleDistribution[]
  priority_work_items: DashboardPriorityWorkItem[]
  upcoming_events: Array<{ date: string; title: string; employee_name?: string; type: string }>
  risk_employees: DashboardRiskEmployee[]
}
