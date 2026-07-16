// 花名册导入相关的 TypeScript 类型定义
// 与后端 schemas/roster_import.py 对应

export interface RosterUploadResponse {
  batch_id: number
  batch_no: string
  file_name: string
  file_size: number
  file_sha256: string
  sheet_names: string[]
  selected_sheet: string | null
  header_row: number
  total_rows: number
  status: string
  message: string
  suggestion: string | null
}

export interface ColumnMapping {
  source_header: string
  source_header_normalized: string
  target_field_key: string | null
  is_mapped: boolean
  is_required: boolean
  is_unknown: boolean
  save_as_alias: boolean
}

export interface FieldDefinition {
  key: string
  label: string
  required: boolean
  description: string
  example_values: string
}

export interface SaveMappingRequest {
  mappings: Record<string, string | null>
}

export interface PreviewSummary {
  new_count: number
  update_count: number
  unchanged_count: number
  confirmation_count: number
  error_count: number
  skipped_count: number
  blocker_count: number
  warning_count: number
  total_rows: number
}

export interface DiffField {
  field_key?: string
  field_label?: string
  old_value?: unknown
  new_value?: unknown
  change_type?: string
}

export interface RowPreviewItem {
  row_no: number
  employee_id: number | null
  normalized_name: string | null
  matched_employee_name: string | null
  row_status: string
  diff_fields: DiffField[]
  issues: IssueItem[]
  can_skip: boolean
  actions: string[]
}

export interface IssueItem {
  id: number
  row_id: number | null
  employee_id: number | null
  field_key: string | null
  issue_code: string
  severity: string
  title: string
  message: string | null
  old_value: unknown
  new_value: unknown
  allowed_actions: string[]
  resolution_status: string
  resolution_action?: string | null
  resolution_value_json?: unknown
  resolution_note?: string | null
  resolved_at?: string | null
  row_no: number | null
  employee_name: string | null
  created_at?: string | null
  updated_at?: string | null
  // 推荐处理字段
  source_value?: string | null
  system_value?: string | null
  recommended_action?: string | null
  recommended_value?: unknown
  recommendation_text?: string | null
  auto_fixable?: boolean
  requires_business_update?: boolean
}

export interface PreviewResponse {
  batch_id: number
  mode: string
  summary: PreviewSummary
  rows: RowPreviewItem[]
  field_definitions: FieldDefinition[]
  current_mappings: Record<string, string>
}

export interface BatchListItem {
  id: number
  batch_no: string
  mode: string
  file_name: string
  file_sha256: string
  batch_status: string
  total_rows: number
  new_count: number
  update_count: number
  skipped_count: number
  confirmation_count: number
  error_count: number
  warning_count: number
  created_at: string
  completed_at: string | null
  failed_at: string | null
  rolled_back_at: string | null
}

export interface CommitConfirmation {
  will_create: number
  will_update: number
  will_create_changes: number
  will_create_compensations: number
  will_create_notes: number
  will_create_confirmations: number
  will_skip: number
}

export interface CommitResponse {
  batch_id: number
  batch_no: string
  status: string
  message: string
  summary: PreviewSummary | null
}

export interface ResolveIssueRequest {
  action: string
  value?: unknown
  note?: string
}

export interface RollbackItem {
  employee_id: number
  employee_name: string
  action: string
  details: string
  reversible: boolean
  conflict: boolean
  conflict_reason: string | null
}

export interface RollbackPreviewResponse {
  batch_id: number
  batch_no: string
  can_rollback: boolean
  items: RollbackItem[]
  irreversible_operations: string[]
  conflicts: string[]
}

export interface BatchResolveRequest {
  issue_ids: number[]
  action: 'APPLY_RECOMMENDATION' | 'IGNORE'
  note?: string
}

export interface BatchResolveResponse {
  total: number
  resolved: number
  skipped: number
  conflicts: Array<{
    issue_id: number
    issue_code: string
    reason: string
  }>
  failed_ids: number[]
}

export interface ColumnAliasItem {
  id: number
  source_header_normalized: string
  target_field_key: string
  enabled: boolean
}

export interface ValueAliasItem {
  id: number
  field_key: string
  source_value_normalized: string
  target_value: string
}
