// 异动与离职DTO

export interface MovementRecord {
  id: number
  employee_name: string
  employment_id: number
  employee_id: number | null
  change_type: string
  before_data: Record<string, any> | null
  after_data: Record<string, any> | null
  effective_date: string | null
  reason: string | null
  confirmed_by: string | null
  confirmed_at: string | null
  created_at: string | null
  department: string | null
  position: string | null
}

export interface SeparationRecord {
  id: number
  employee_name: string
  employment_id: number
  employee_id: number | null
  separation_type: string | null
  planned_separation_date: string | null
  actual_separation_date: string | null
  reason: string | null
  hr_comment: string | null
  confirmed_by: string | null
  confirmed_at: string | null
  created_at: string | null
  department: string | null
  position: string | null
}

export interface MovementResponse {
  changes: MovementRecord[]
  separations: SeparationRecord[]
}
