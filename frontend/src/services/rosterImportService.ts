import api from '@/api'
import type { ApiResponse, PageParams, PaginatedData } from '@/types/common'
import type {
  BatchListItem,
  ColumnAliasItem,
  ColumnMapping,
  CommitResponse,
  FieldDefinition,
  IssueItem,
  PreviewResponse,
  ResolveIssueRequest,
  RosterUploadResponse,
  ValueAliasItem,
  RollbackPreviewResponse,
} from '@/types/roster-import'

const BASE = '/roster-imports'

/**
 * 上传花名册文件
 */
export async function uploadRoster(
  file: File,
  mode: 'INITIALIZE' | 'SYNC' = 'SYNC',
  sheetName?: string,
): Promise<RosterUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', mode)
  if (sheetName) {
    formData.append('sheet_name', sheetName)
  }
  // 上传不能设置 Content-Type，让浏览器自动生成 boundary
  const res = await api.post(`${BASE}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data.data
}

/**
 * 导入批次列表
 */
export async function listBatches(params: PageParams): Promise<PaginatedData<BatchListItem>> {
  const res = await api.get(BASE, { params })
  return res.data.data
}

/**
 * 导入批次详情
 */
export async function getBatchDetail(batchId: number): Promise<Record<string, unknown>> {
  const res = await api.get(`${BASE}/${batchId}`)
  return res.data.data
}

/**
 * 获取批次行
 */
export async function getBatchRows(
  batchId: number,
  params: { status?: string; page?: number; page_size?: number },
): Promise<PaginatedData<Record<string, unknown>>> {
  const res = await api.get(`${BASE}/${batchId}/rows`, { params })
  return res.data.data
}

/**
 * 获取批次问题
 */
export async function getBatchIssues(
  batchId: number,
  params?: { severity?: string; status?: string },
): Promise<{ items: IssueItem[] }> {
  const res = await api.get(`${BASE}/${batchId}/issues`, { params })
  return res.data.data
}

/**
 * 保存字段映射
 */
export async function saveMapping(
  batchId: number,
  data: { mappings: Record<string, string | null> },
): Promise<{ batch_id: number; mapped_count: number; unmapped_count: number; unmapped_required: string[] }> {
  const res = await api.post(`${BASE}/${batchId}/mapping`, data)
  return res.data.data
}

/**
 * 生成导入预览
 */
export async function generatePreview(batchId: number): Promise<PreviewResponse> {
  const res = await api.post(`${BASE}/${batchId}/preview`)
  return res.data.data
}

/**
 * 处理问题
 */
export async function resolveIssue(
  batchId: number,
  issueId: number,
  data: ResolveIssueRequest,
): Promise<IssueItem> {
  const res = await api.patch(`${BASE}/${batchId}/issues/${issueId}`, data)
  return res.data.data
}

/**
 * 提交导入
 */
export async function commitImport(batchId: number): Promise<CommitResponse> {
  const res = await api.post(`${BASE}/${batchId}/commit`)
  return res.data.data
}

/**
 * 撤销预览
 */
export async function getRollbackPreview(batchId: number): Promise<RollbackPreviewResponse> {
  const res = await api.get(`${BASE}/${batchId}/rollback-preview`)
  return res.data.data
}

/**
 * 执行撤销
 */
export async function executeRollback(batchId: number): Promise<Record<string, unknown>> {
  const res = await api.post(`${BASE}/${batchId}/rollback`)
  return res.data.data
}

/**
 * 下载原始文件
 */
export function getFileDownloadUrl(batchId: number): string {
  return `${api.defaults.baseURL}${BASE}/${batchId}/file`
}

/**
 * 获取字段定义
 */
export async function getFieldDefinitions(): Promise<FieldDefinition[]> {
  const res = await api.get(`${BASE}/field-definitions`)
  return res.data.data
}

/**
 * 获取列别名
 */
export async function listColumnAliases(): Promise<ColumnAliasItem[]> {
  const res = await api.get(`${BASE}/column-aliases`)
  return res.data.data
}

/**
 * 创建列别名
 */
export async function createColumnAlias(data: {
  source_header_normalized: string
  target_field_key: string
}): Promise<ColumnAliasItem> {
  const res = await api.post(`${BASE}/column-aliases`, data)
  return res.data.data
}

/**
 * 获取值别名
 */
export async function listValueAliases(fieldKey?: string): Promise<ValueAliasItem[]> {
  const res = await api.get(`${BASE}/value-aliases`, { params: { field_key: fieldKey } })
  return res.data.data
}

/**
 * 创建值别名
 */
export async function createValueAlias(data: {
  field_key: string
  source_value_normalized: string
  target_value: string
}): Promise<ValueAliasItem> {
  const res = await api.post(`${BASE}/value-aliases`, data)
  return res.data.data
}
