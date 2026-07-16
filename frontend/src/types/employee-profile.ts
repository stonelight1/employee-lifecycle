// 员工扩展资料相关的 TypeScript 类型定义
// 与后端 schemas/employee_profile.py 对应

export interface EmployeeProfile {
  id?: number
  employee_id: number
  identity_card?: string | null
  gender?: string | null
  birth_date?: string | null
  household_registration?: string | null
  residence_address?: string | null
  household_type?: string | null
  graduation_school?: string | null
  major?: string | null
  education_level?: string | null
  social_insurance_policy?: string | null
  housing_fund_policy?: string | null
  social_insurance_status?: string | null
  housing_fund_status?: string | null
  social_insurance_start_date?: string | null
  housing_fund_start_date?: string | null
  benefit_raw_text?: string | null
}

export interface AttributeHistoryItem {
  id: number
  employee_id: number
  field_name: string
  before_value?: unknown
  after_value?: unknown
  effective_date?: string | null
  source_type: string
  operator_name?: string | null
  created_at?: string | null
}

export interface FinancialAccount {
  id: number
  employee_id: number
  account_type: 'BANK' | 'ALIPAY'
  account_no: string
  bank_name?: string | null
  is_primary: boolean
  account_status: 'ACTIVE' | 'INACTIVE'
  source_type: string
  confirmed_at?: string | null
  created_at?: string | null
}

export interface EmploymentContract {
  id: number
  employee_id: number
  employment_id?: number | null
  contract_status?: string | null
  signing_company?: string | null
  contract_type?: 'FIXED_TERM' | 'INDEFINITE' | 'UNKNOWN' | null
  start_date?: string | null
  end_date?: string | null
  signing_sequence?: number | null
  source_type: string
  confirmed_at?: string | null
  created_at?: string | null
}

export interface Compensation {
  id: number
  employee_id: number
  employment_id?: number | null
  raw_salary_text?: string | null
  salary_type?: 'MONTHLY' | 'DAILY' | 'MIXED' | 'UNKNOWN' | null
  base_salary?: number | null
  probation_salary?: number | null
  regular_salary?: number | null
  daily_rate?: number | null
  performance_amount?: number | null
  performance_ratio?: number | null
  commission_text?: string | null
  other_text?: string | null
  effective_date?: string | null
  source_type: string
  created_at?: string | null
}

export interface EmployeeAssessment {
  id: number
  employee_id: number
  assessment_type: 'MBTI' | 'PDP'
  result_text?: string | null
  attachment_path?: string | null
  assessment_date?: string | null
  source_type: string
  created_at?: string | null
}

export interface EmployeeNote {
  id: number
  employee_id: number
  employment_id?: number | null
  content: string
  source_type: string
  source_row_no?: number | null
  created_at?: string | null
}

export interface FullProfile {
  employee: Record<string, unknown>
  profile?: EmployeeProfile | null
  current_employment?: Record<string, unknown> | null
  all_employments: Record<string, unknown>[]
  contracts: EmploymentContract[]
  financial_accounts: FinancialAccount[]
  compensations: Compensation[]
  assessments: EmployeeAssessment[]
  notes: EmployeeNote[]
  attribute_history: AttributeHistoryItem[]
}
