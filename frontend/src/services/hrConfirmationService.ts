import { get, post } from '@/api'
import type { ConfirmationItem, ConfirmationListResponse, ConfirmActionRequest } from '@/types/hr-confirmation'

const BASE = '/hr-confirmations'

/**
 * 获取待确认事项列表
 */
export async function listConfirmations(
  params: { status?: string; employee_id?: number; page?: number; page_size?: number } = {},
): Promise<ConfirmationListResponse> {
  const res = await get<ConfirmationListResponse>(BASE, params)
  if (!res.success || !res.data) {
    return { items: [], total: 0, pending_count: 0 }
  }
  return res.data
}

/**
 * 获取待确认数量
 */
export async function getPendingCount(): Promise<{ pending_count: number }> {
  const res = await get<{ pending_count: number }>(`${BASE}/pending-count`)
  if (!res.success || !res.data) {
    return { pending_count: 0 }
  }
  return res.data
}

/**
 * 获取确认事项详情
 */
export async function getConfirmationDetail(id: number): Promise<ConfirmationItem> {
  const res = await get<ConfirmationItem>(`${BASE}/${id}`)
  if (!res.success || !res.data) {
    throw new Error('获取确认事项详情失败')
  }
  return res.data
}

/**
 * 确认
 */
export async function confirmItem(id: number, note?: string): Promise<ConfirmationItem> {
  const res = await post<ConfirmationItem>(`${BASE}/${id}/confirm`, { note } as ConfirmActionRequest)
  if (!res.success || !res.data) {
    throw new Error('确认操作失败')
  }
  return res.data
}

/**
 * 拒绝
 */
export async function rejectItem(id: number, note?: string): Promise<ConfirmationItem> {
  const res = await post<ConfirmationItem>(`${BASE}/${id}/reject`, { note } as ConfirmActionRequest)
  if (!res.success || !res.data) {
    throw new Error('拒绝操作失败')
  }
  return res.data
}

/**
 * 忽略
 */
export async function ignoreItem(id: number, note?: string): Promise<ConfirmationItem> {
  const res = await post<ConfirmationItem>(`${BASE}/${id}/ignore`, { note } as ConfirmActionRequest)
  if (!res.success || !res.data) {
    throw new Error('忽略操作失败')
  }
  return res.data
}
