// 生命周期相关DTO

export type LifecycleStage =
  | 'PENDING'
  | 'PROBATION'
  | 'REGULARIZATION_PENDING'
  | 'ACTIVE'
  | 'SEPARATING'
  | 'SEPARATED'
  | 'UNKNOWN'

/** 员工当前任职摘要（从后端聚合接口返回） */
export interface CurrentEmploymentSummary {
  id: number
  department: string | null
  position: string | null
  hire_date: string
  employment_status: string
  probation_status: string
  probation_start_date: string | null
  probation_end_date: string | null
  expected_regularization_date: string | null
}

/** 员工下一步行动 */
export interface NextAction {
  id: number
  source_type: string
  title: string
  due_at: string | null
  status: string
}

/** 包含当前任职信息的员工行（用于列表展示） */
export interface EmployeeWithLifecycle {
  id: number
  name: string
  employee_no: string | null
  mobile: string | null
  employee_status: string
  lifecycle_stage: LifecycleStage
  risk_level: string
  risk_reason?: string
  current_employment: CurrentEmploymentSummary | null
  next_action: NextAction | null
  created_at: string
  probation_progress: number
}
