import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

/**
 * 格式化日期：YYYY-MM-DD
 */
export function formatDate(date?: string | Date | null): string {
  if (!date) return '—'
  return dayjs(date).format('YYYY-MM-DD')
}

/**
 * 格式化日期时间：YYYY-MM-DD HH:mm:ss
 */
export function formatDateTime(date?: string | Date | null): string {
  if (!date) return '—'
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

/**
 * 相对时间：今天、明天、3天后、已逾期2天
 */
export function formatRelativeDate(date?: string | Date | null): string {
  if (!date) return '—'
  const d = dayjs(date)
  const now = dayjs()
  const diffDays = d.diff(now, 'day')

  if (d.isSame(now, 'day')) return '今天'
  if (d.isSame(now.add(1, 'day'), 'day')) return '明天'
  if (d.isSame(now.subtract(1, 'day'), 'day')) return '昨天'

  if (diffDays > 0) return `${diffDays} 天后`
  if (diffDays < 0) return `已逾期 ${Math.abs(diffDays)} 天`
  return '今天'
}

/**
 * 计算逾期天数
 */
export function calculateOverdueDays(dueDate?: string | Date | null): number {
  if (!dueDate) return 0
  const d = dayjs(dueDate)
  const now = dayjs()
  if (d.isBefore(now, 'day')) {
    return now.diff(d, 'day')
  }
  return 0
}

/**
 * 计算在职时长
 */
export function formatTenure(hireDate?: string | Date | null): string {
  if (!hireDate) return '—'
  const start = dayjs(hireDate)
  const now = dayjs()
  const months = now.diff(start, 'month')
  const days = now.diff(start.add(months, 'month'), 'day')
  if (months === 0) return `${days} 天`
  return `${months} 个月 ${days} 天`
}

/**
 * 计算试用期进度百分比 (0-100)
 */
export function calculateProbationProgress(
  hireDate?: string | Date | null,
  probationEndDate?: string | Date | null,
): number {
  if (!hireDate || !probationEndDate) return 0
  const start = dayjs(hireDate)
  const end = dayjs(probationEndDate)
  const now = dayjs()

  const totalDays = end.diff(start, 'day')
  if (totalDays <= 0) return 100

  const elapsedDays = now.diff(start, 'day')
  const progress = Math.round((elapsedDays / totalDays) * 100)
  return Math.min(100, Math.max(0, progress))
}

/**
 * 计算超期天数（超过预计日期仍未处理）
 */
export function calculateOverdueText(dueDate?: string | Date | null): string | null {
  if (!dueDate) return null
  const days = calculateOverdueDays(dueDate)
  if (days > 0) return `已超期 ${days} 天`
  return null
}

/**
 * 表格中使用简洁日期，悬停显示完整时间
 */
export function tableDate(date?: string | Date | null): string {
  if (!date) return '—'
  return dayjs(date).format('MM-DD')
}
