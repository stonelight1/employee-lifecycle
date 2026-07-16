// 风险对象（列表聚合返回）
export interface RiskInfo {
  level: string | null
  reason: string | null
  assessed_at: string | null
}

// 任职摘要（列表聚合返回）
export interface EmploymentSummary {
  id: number
  department?: string | null
  position?: string | null
  team_name?: string | null
  employment_status: string
  hire_date?: string | null
  expected_hire_date?: string | null
  actual_hire_date?: string | null
  probation_status: string
  probation_start_date?: string | null
  probation_end_date?: string | null
  expected_regularization_date?: string | null
  actual_regularization_date?: string | null
  actual_separation_date?: string | null
}

// 下一事项（列表聚合返回）
export interface NextActionInfo {
  id: number
  source_type: string
  title: string
  due_at: string | null
  status: string
  days_until_due: number | null
  overdue_days: number
}

// 员工列表聚合项（后端 list_employees 统一返回）
export interface EmployeeListItem {
  id: number
  name: string
  employee_no?: string | null
  mobile?: string | null
  email?: string | null
  gender?: string | null
  birth_date?: string | null
  employee_status: string
  lifecycle_stage: string
  current_employment: EmploymentSummary | null
  probation_progress: number | null
  risk: RiskInfo
  next_action: NextActionInfo | null
  identity_card?: string | null
  signing_company?: string | null
}

// 员工列表分页响应
export interface EmployeeListData {
  items: EmployeeListItem[]
  total: number
  page: number
  page_size: number
}
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: ApiError
  request_id?: string
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, any>
}

// 员工
export interface EmployeeItem {
  id: number
  employee_no?: string
  name: string
  normalized_name: string
  mobile?: string
  email?: string
  employee_status: string
  source?: string
  created_at: string
  updated_at?: string
  is_deleted: boolean
}

// 任职
export interface EmploymentItem {
  id: number
  employee_id: number
  employment_seq: number
  employment_status: string
  hire_date: string
  probation_start_date?: string
  probation_end_date?: string
  probation_status: string
  department?: string
  position?: string
  manager_name?: string
  regularization_date?: string
  separation_date?: string
}

// 跟进任务
export interface FollowupTaskItem {
  id: number
  employment_id: number
  task_name: string
  followup_status: string
  planned_date: string
  confirmation_mode: string
  node_code_snapshot?: string
  offset_days_snapshot?: number
  completed_at?: string
  cancel_reason?: string
}

// 沟通记录
export interface CommunicationItem {
  id: number
  employment_id: number
  followup_task_id?: number
  communication_type?: string
  communication_status: string
  current_text_version_id?: number
  current_text_version_no?: number
  current_text_hash?: string
  manual_summary?: string
  hr_conclusion?: string
  ai_summary_is_stale?: boolean
  created_at: string
}

// AI 总结
export interface AiSummaryItem {
  id: number
  communication_id: number
  version_no: number
  source_text_version_id?: number
  summary_status: string
  structured_summary?: string
  is_ai_suggestion: boolean
  is_current: boolean
  is_stale: boolean
  created_at: string
}

// 风险评估
export interface RiskAssessmentItem {
  id: number
  communication_id: number
  assessment_source: string
  ai_risk_level?: string
  ai_risk_reasons?: string
  risk_review_status: string
  hr_risk_level?: string
  hr_comment?: string
  reviewed_by?: string
  is_current: boolean
}

// 试用期评估
export interface ProbationReviewItem {
  id: number
  employment_id: number
  followup_task_id?: number
  communication_id?: number
  review_seq: number
  review_stage: string
  review_status?: string
  hr_evaluation?: string
  employee_feedback?: string
  recommendation?: string
  reviewed_by?: string
  reviewed_at?: string
  created_at?: string
  created_by?: string
  version: number
}

// 转正记录
export interface RegularizationItem {
  id: number
  employment_id: number
  decision: string
  effective_date?: string
  new_probation_end_date?: string
  decision_reason?: string
  ai_summary_version_id?: number
  confirmed_by?: string
  confirmed_at?: string
  is_effective: boolean
  version: number
}

// 离职记录
export interface SeparationItem {
  id: number
  employment_id: number
  planned_separation_date?: string
  actual_separation_date?: string
  separation_type?: string
  reason?: string
  hr_comment?: string
  confirmed_by?: string
  confirmed_at?: string
  version: number
}

// 异动记录
export interface EmploymentChangeItem {
  id: number
  employment_id: number
  change_type: string
  effective_date: string
  before_data?: Record<string, any> | string
  after_data?: Record<string, any> | string
  reason?: string
  confirmed_by?: string
  confirmed_at?: string
  created_at: string
  version: number
}

// 文本版本
export interface TextVersionItem {
  id: number
  communication_id: number
  version_no: number
  text_content: string
  text_hash: string
  text_length: number
  change_reason?: string
  created_at: string
  created_by?: string
}

// 待办
export interface TodoItem {
  id: number
  user_id: string
  business_type: string
  business_id: number
  title: string
  due_at?: string
  todo_status: string
  priority?: string
}

// 操作日志
export interface LogItem {
  id: number
  operator_id: string
  operated_at: string
  object_type: string
  object_id: string
  operation_type: string
  operation_source?: string
}
