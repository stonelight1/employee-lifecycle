/**
 * 日期工具测试
 *
 * 必须使用固定时间：
 *   vi.setSystemTime(new Date('2026-07-16T10:00:00+08:00'))
 *
 * 覆盖场景：
 *   昨天、今天、明天、7天后、8天后、跨月、跨年、无日期、非法日期、
 *   包含时分秒、纯 YYYY-MM-DD
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import {
  formatDate,
  formatDateTime,
  formatRelativeDate,
  calculateOverdueDays,
  calculateProbationProgress,
  calculateOverdueText,
  formatTenure,
} from '@/utils/date'
import dayjs from 'dayjs'

// 固定当前时间：2026-07-16 10:00 CST (UTC+8)
const FIXED_NOW = new Date('2026-07-16T10:00:00+08:00')

beforeAll(() => {
  vi.useFakeTimers()
  vi.setSystemTime(FIXED_NOW)
})

afterAll(() => {
  vi.useRealTimers()
})

describe('formatDate', () => {
  it('正常日期格式化为 YYYY-MM-DD', () => {
    expect(formatDate('2026-07-16')).toBe('2026-07-16')
  })

  it('包含时分秒的日期', () => {
    expect(formatDate('2026-07-16T10:00:00')).toBe('2026-07-16')
  })

  it('null 和 undefined 返回 —', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
  })

  it('非法日期返回 —', () => {
    expect(formatDate('not-a-date')).toBe('—')
  })

  it('跨月日期', () => {
    expect(formatDate('2026-08-01')).toBe('2026-08-01')
    expect(formatDate('2026-06-30')).toBe('2026-06-30')
  })

  it('跨年日期', () => {
    expect(formatDate('2027-01-01')).toBe('2027-01-01')
    expect(formatDate('2025-12-31')).toBe('2025-12-31')
  })
})

describe('formatDateTime', () => {
  it('格式化为 YYYY-MM-DD HH:mm:ss', () => {
    expect(formatDateTime('2026-07-16T10:00:00')).toBe('2026-07-16 10:00:00')
  })

  it('null 返回 —', () => {
    expect(formatDateTime(null)).toBe('—')
  })

  it('非法日期返回 —', () => {
    expect(formatDateTime('not-a-date')).toBe('—')
  })
})

describe('formatRelativeDate', () => {
  it('今天返回"今天"', () => {
    expect(formatRelativeDate('2026-07-16')).toBe('今天')
  })

  it('明天返回"明天"', () => {
    expect(formatRelativeDate('2026-07-17')).toBe('明天')
  })

  it('昨天返回"昨天"', () => {
    expect(formatRelativeDate('2026-07-15')).toBe('昨天')
  })

  it('7天后返回"7 天后"', () => {
    expect(formatRelativeDate('2026-07-23')).toBe('7 天后')
  })

  it('8天后返回"8 天后"', () => {
    expect(formatRelativeDate('2026-07-24')).toBe('8 天后')
  })

  it('已逾期2天', () => {
    expect(formatRelativeDate('2026-07-14')).toBe('已逾期 2 天')
  })

  it('null 返回 —', () => {
    expect(formatRelativeDate(null)).toBe('—')
  })

  it('非法日期返回 —', () => {
    expect(formatRelativeDate('not-a-date')).toBe('—')
  })
})

describe('calculateOverdueDays', () => {
  it('今天到期的返回 0', () => {
    expect(calculateOverdueDays('2026-07-16')).toBe(0)
  })

  it('明天到期的返回 0', () => {
    expect(calculateOverdueDays('2026-07-17')).toBe(0)
  })

  it('昨天到期的返回 1', () => {
    expect(calculateOverdueDays('2026-07-15')).toBe(1)
  })

  it('7天前到期的返回 7', () => {
    expect(calculateOverdueDays('2026-07-09')).toBe(7)
  })

  it('null 返回 0', () => {
    expect(calculateOverdueDays(null)).toBe(0)
  })

  it('非法日期返回 0', () => {
    expect(calculateOverdueDays('not-a-date')).toBe(0)
  })
})

describe('calculateProbationProgress', () => {
  it('已过试用期一半', () => {
    // 2026-06-01 到 2026-09-01，总共 92 天
    // 从 06-01 到 07-16 = 45 天
    // 45/92 ≈ 48.9% → 49%
    const progress = calculateProbationProgress('2026-06-01', '2026-09-01')
    expect(progress).toBeGreaterThan(40)
    expect(progress).toBeLessThan(60)
  })

  it('刚开始试用期返回接近 0', () => {
    const progress = calculateProbationProgress('2026-07-16', '2026-10-16')
    expect(progress).toBeLessThan(5)
  })

  it('试用期已结束返回 100', () => {
    const progress = calculateProbationProgress('2026-01-01', '2026-04-01')
    expect(progress).toBe(100)
  })

  it('缺少日期返回 0', () => {
    expect(calculateProbationProgress(null, null)).toBe(0)
    expect(calculateProbationProgress('2026-01-01', null)).toBe(0)
  })

  it('非法日期返回 0', () => {
    expect(calculateProbationProgress('not-a-date', '2026-09-01')).toBe(0)
  })

  it('结束日期早于开始日期返回 100', () => {
    const progress = calculateProbationProgress('2026-07-16', '2026-01-01')
    expect(progress).toBe(100)
  })
})

describe('calculateOverdueText', () => {
  it('已逾期返回文本', () => {
    expect(calculateOverdueText('2026-07-14')).toBe('已超期 2 天')
  })

  it('未逾期返回 null', () => {
    expect(calculateOverdueText('2026-07-17')).toBeNull()
  })

  it('null 返回 null', () => {
    expect(calculateOverdueText(null)).toBeNull()
  })
})

describe('formatTenure', () => {
  it('在职1个月', () => {
    const tenure = formatTenure('2026-06-16')
    expect(tenure).toContain('1 个月')
  })

  it('在职0个月', () => {
    const tenure = formatTenure('2026-07-14')
    expect(tenure).toContain('2 天')
  })

  it('null 返回 —', () => {
    expect(formatTenure(null)).toBe('—')
  })

  it('非法日期返回 —', () => {
    expect(formatTenure('not-a-date')).toBe('—')
  })
})
