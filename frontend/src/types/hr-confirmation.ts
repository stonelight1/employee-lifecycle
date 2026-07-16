// HR 待确认事项相关的 TypeScript 类型定义

export interface ConfirmationItem {
  id: number
  employee_id: number
  employee_name?: string | null
  employment_id?: number | null
  source_type: string
  source_id?: string | null
  issue_code: string
  title: string
  description?: string | null
  before_data?: unknown
  after_data?: unknown
  item_status: 'PENDING' | 'CONFIRMED' | 'REJECTED' | 'IGNORED'
  created_at: string
  handled_at?: string | null
}

export interface ConfirmationListResponse {
  items: ConfirmationItem[]
  total: number
  pending_count: number
}

export interface ConfirmActionRequest {
  note?: string
  action_data?: Record<string, unknown>
}
