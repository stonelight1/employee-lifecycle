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

// 合同类型映射
export const contractTypeMap: Record<string, string> = {
  FIXED_TERM: '固定期限',
  INDEFINITE: '无固定期限',
  UNKNOWN: '未知',
}

// 合同状态映射
export const contractStatusMap: Record<string, string> = {
  SIGNED: '已签订',
  ACTIVE: '有效',
  EXPIRED: '已到期',
  TERMINATED: '已终止',
  NOT_SIGNED: '未签订',
}

// 账户类型映射
export const accountTypeMap: Record<string, string> = {
  BANK: '银行卡',
  ALIPAY: '支付宝',
}

// 账户状态映射
export const accountStatusMap: Record<string, string> = {
  ACTIVE: '有效',
  INACTIVE: '无效',
}

// 薪资类型映射
export const salaryTypeMap: Record<string, string> = {
  MONTHLY: '月薪',
  DAILY: '日薪',
  MIXED: '混合',
  UNKNOWN: '未知',
}

// 评估类型映射
export const assessmentTypeMap: Record<string, string> = {
  MBTI: 'MBTI',
  PDP: 'PDP',
}

// 性别映射
export const genderMap: Record<string, string> = {
  MALE: '男',
  FEMALE: '女',
}

// 户口类型映射
export const householdTypeMap: Record<string, string> = {
  URBAN: '城镇',
  RURAL: '农村',
  OTHER: '其他',
}

// 学历映射
export const educationLevelMap: Record<string, string> = {
  DOCTORATE: '博士',
  MASTER: '硕士',
  BACHELOR: '本科',
  COLLEGE: '大专',
  HIGH_SCHOOL: '高中',
  JUNIOR_HIGH: '初中',
  OTHER: '其他',
}

// 办公方式映射
export const workModeMap: Record<string, string> = {
  ON_SITE: '现场办公',
  REMOTE: '远程办公',
  HYBRID: '混合办公',
  OTHER: '其他',
}

// 员工类型映射
export const employmentTypeMap: Record<string, string> = {
  FULL_TIME: '全职',
  PART_TIME: '兼职',
  CONTRACTOR: '外包',
  INTERN: '实习',
  OTHER: '其他',
}

// 社保状态映射
export const socialInsuranceStatusMap: Record<string, string> = {
  ACTIVE: '正常缴纳',
  PENDING: '待缴纳',
  NOT_PROVIDED: '不缴纳',
  UNKNOWN: '无法判断',
  INACTIVE: '未缴纳',
  SUSPENDED: '暂停缴纳',
}

// 公积金状态映射
export const housingFundStatusMap: Record<string, string> = {
  ACTIVE: '正常缴纳',
  PENDING: '待缴纳',
  NOT_PROVIDED: '不缴纳',
  UNKNOWN: '无法判断',
  INACTIVE: '未缴纳',
  SUSPENDED: '暂停缴纳',
}

export const benefitPolicyMap: Record<string, string> = {
  FROM_HIRE_DATE: '从入职日开始',
  FROM_REGULARIZATION_DATE: '从转正日开始',
  NOT_PROVIDED: '不缴纳',
  UNKNOWN: '无法判断',
}

// 操作日志对象类型映射
export const operationObjectTypeMap: Record<string, string> = {
  EMPLOYEE: '员工',
  EMPLOYMENT: '任职',
  FOLLOWUP_NODE: '跟进节点',
  FOLLOWUP_TASK: '跟进任务',
  COMMUNICATION: '沟通记录',
  AI_SUMMARY: 'AI 总结',
  RISK_ASSESSMENT: '风险评估',
  PROBATION_REVIEW: '试用期评估',
  REGULARIZATION: '转正',
  EMPLOYMENT_CHANGE: '异动',
  SEPARATION: '离职',
  TODO: '待办',
  ROSTER_IMPORT: '花名册导入',
  ROSTER_ISSUE: '花名册问题',
  HR_CONFIRMATION: 'HR 确认',
  EMPLOYEE_PROFILE: '员工资料',
  CONTRACT: '合同',
  FINANCIAL_ACCOUNT: '财务账户',
  COMPENSATION: '薪酬',
  ASSESSMENT: '测评',
  NOTE: '备注',
  ATTRIBUTE_HISTORY: '属性变更历史',
  SEPARATION_CHECKLIST: '离职清单',
  ORGANIZATION_REFERENCE: '组织参考',
}

// 沟通类型映射
export const communicationTypeMap: Record<string, string> = {
  PROBATION_FOLLOWUP: '试用期跟进',
  REGULARIZATION_INTERVIEW: '转正面谈',
  SEPARATION_TALK: '离职面谈',
  ONBOARDING: '入职沟通',
  GENERAL: '一般沟通',
}

// 任务来源映射
export const taskSourceMap: Record<string, string> = {
  AUTO: '系统自动',
  MANUAL: '手动创建',
}

// 试用期评估状态映射
export const reviewStatusMap: Record<string, string> = {
  DRAFT: '草稿',
  COMPLETED: '已完成',
}

// 资料完整性映射
export const profileCompletenessMap: Record<string, string> = {
  COMPLETE: '资料完整',
  INCOMPLETE: '资料不完整',
}

// 通用状态获取函数
export function getStatusLabel(
  map: Record<string, string>,
  value?: string | null,
): string {
  if (!value) return '—'
  return map[value] ?? value
}

// 开发环境警告
export function getStatusLabelWithWarning(
  map: Record<string, string>,
  value?: string | null,
): string {
  if (!value) return '—'
  const label = map[value]
  if (!label && import.meta.env.DEV) {
    console.warn(`[Status] 未映射的状态值: "${value}"，可用的键: ${Object.keys(map).join(', ')}`)
  }
  return label ?? value
}
