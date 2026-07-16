// 生命周期阶段颜色与标签（与后端 resolve_lifecycle_stage 一致）
export const lifecycleStageMap: Record<string, { label: string; color: string; background: string }> = {
  PENDING: { label: '待入职', color: '#7C3AED', background: '#F3E8FF' },
  PROBATION: { label: '试用期', color: '#2563EB', background: '#EFF6FF' },
  REGULARIZATION_PENDING: { label: '待转正', color: '#D97706', background: '#FFF7E8' },
  ACTIVE: { label: '正式在职', color: '#16825D', background: '#EAF8F1' },
  SEPARATING: { label: '离职中', color: '#E11D48', background: '#FFF1F2' },
  SEPARATED: { label: '已离职', color: '#667085', background: '#F2F4F7' },
  UNKNOWN: { label: '未知', color: '#98A2B3', background: '#F2F4F7' },
}

// 风险等级
export const riskMap: Record<string, { label: string; color: string; background: string }> = {
  HIGH: { label: '高风险', color: '#C01048', background: '#FFF1F3' },
  MEDIUM: { label: '需关注', color: '#B54708', background: '#FFFAEB' },
  LOW: { label: '低风险', color: '#175CD3', background: '#EFF8FF' },
  NONE: { label: '正常', color: '#027A48', background: '#ECFDF3' },
}

// 后端 EmploymentStatus 映射
export const employmentStatusMap: Record<string, string> = {
  PENDING: '待入职',
  ACTIVE: '在职',
  SEPARATING: '离职办理中',
  SEPARATED: '已离职',
}

// 后端 EmployeeStatus 映射
export const employeeStatusMap: Record<string, string> = {
  ACTIVE: '在职',
  ARCHIVED: '已归档',
}

// 后端 ProbationStatus 映射
export const probationStatusMap: Record<string, string> = {
  NOT_STARTED: '未开始',
  IN_PROGRESS: '进行中',
  PENDING_REVIEW: '待转正',
  REGULARIZED: '已转正',
  FAILED: '未通过',
  TERMINATED: '已终止',
}

// 跟进任务状态映射
export const followupStatusMap: Record<string, string> = {
  PENDING: '待处理',
  IN_PROGRESS: '处理中',
  PENDING_CONFIRMATION: '待确认',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
}

// 待办状态映射
export const todoStatusMap: Record<string, string> = {
  PENDING: '待处理',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
}

// 确认模式映射
export const confirmationModeMap: Record<string, string> = {
  ALL: '全部确认',
  ANY: '任意确认',
}

// 沟通状态映射
export const communicationStatusMap: Record<string, string> = {
  DRAFT: '草稿',
  COMPLETED: '已完成',
  VOIDED: '已作废',
}

// AI 总结状态映射
export const aiSummaryStatusMap: Record<string, string> = {
  PROCESSING: '处理中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
}

// 风险审核状态
export const riskReviewStatusMap: Record<string, string> = {
  PENDING_REVIEW: '待审核',
  CONFIRMED: '已确认',
  MODIFIED: '已修改',
  REJECTED: '已驳回',
}

// 转正决策
export const regularizationDecisionMap: Record<string, string> = {
  APPROVED: '批准转正',
  EXTENDED: '延长试用期',
  NOT_APPROVED: '未通过',
}

// 异动类型
export const changeTypeMap: Record<string, string> = {
  DEPARTMENT: '部门变更',
  POSITION: '岗位变更',
  MANAGER: '负责人变更',
}

// 离职类型
export const separationTypeMap: Record<string, string> = {
  VOLUNTARY: '主动离职',
  NEGOTIATED: '协商解除',
  DISMISSAL: '公司辞退',
  PROBATION_FAIL: '试用期不通过',
  CONTRACT_EXPIRED: '合同到期',
  OTHER: '其他',
}

// 试用期评估阶段
export const reviewStageMap: Record<string, string> = {
  FOLLOWUP: '过程评估',
  FINAL: '最终评估',
}

// 通用状态获取函数
export function getStatusLabel(
  map: Record<string, string>,
  value?: string,
): string {
  if (!value) return '—'
  return map[value] ?? value
}

// 开发环境警告
export function getStatusLabelWithWarning(
  map: Record<string, string>,
  value?: string,
): string {
  if (!value) return '—'
  const label = map[value]
  if (!label && import.meta.env.DEV) {
    console.warn(`[Status] 未映射的状态值: "${value}"，可用的键: ${Object.keys(map).join(', ')}`)
  }
  return label ?? value
}
