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

export interface PageParams {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
