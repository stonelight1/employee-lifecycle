import axios from 'axios'
import type { ApiResponse } from '@/types/common'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// V1 单用户模式：不发送用户身份信息，由后端固定注入操作者

// 响应拦截
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const data = error.response?.data
    if (data?.error) {
      return Promise.reject(new Error(data.error.message || '请求失败'))
    }
    return Promise.reject(error)
  },
)

export async function get<T>(url: string, params?: Record<string, any>): Promise<ApiResponse<T>> {
  const res = await http.get<ApiResponse<T>>(url, { params })
  return res.data
}

export async function post<T>(url: string, data?: any): Promise<ApiResponse<T>> {
  const res = await http.post<ApiResponse<T>>(url, data)
  return res.data
}

export async function patch<T>(url: string, data?: any): Promise<ApiResponse<T>> {
  const res = await http.patch<ApiResponse<T>>(url, data)
  return res.data
}

export async function del<T>(url: string): Promise<ApiResponse<T>> {
  const res = await http.delete<ApiResponse<T>>(url)
  return res.data
}

export async function put<T>(url: string, data?: any): Promise<ApiResponse<T>> {
  const res = await http.put<ApiResponse<T>>(url, data)
  return res.data
}

export default http
