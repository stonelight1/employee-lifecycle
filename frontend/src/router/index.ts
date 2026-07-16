import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  // 工作台
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/DashboardView.vue'),
  },
  // 工作事项
  {
    path: '/work-items',
    name: 'WorkItemCenter',
    component: () => import('@/views/work/WorkItemCenter.vue'),
  },
  // 员工
  {
    path: '/employees',
    name: 'EmployeeList',
    component: () => import('@/views/employee/EmployeeList.vue'),
  },
  {
    path: '/employees/new',
    name: 'EmployeeCreate',
    component: () => import('@/views/employee/EmployeeForm.vue'),
  },
  {
    path: '/employees/:id',
    name: 'EmployeeDetail',
    component: () => import('@/views/employee/EmployeeDetail.vue'),
  },
  {
    path: '/employees/:id/edit',
    name: 'EmployeeEdit',
    component: () => import('@/views/employee/EmployeeForm.vue'),
  },
  {
    path: '/employees/:id/employments/new',
    name: 'EmploymentCreate',
    component: () => import('@/views/employee/EmploymentCreate.vue'),
  },
  {
    path: '/employees/:id/employments/:employmentId',
    name: 'EmploymentDetail',
    component: () => import('@/views/employee/EmploymentDetail.vue'),
  },
  // 试用期中心
  {
    path: '/probation',
    name: 'ProbationCenter',
    component: () => import('@/views/probation/ProbationCenter.vue'),
  },
  // 转正管理
  {
    path: '/regularizations',
    name: 'RegularizationCenter',
    component: () => import('@/views/regularization/RegularizationCenter.vue'),
  },
  // 异动与离职
  {
    path: '/employee-movements',
    name: 'MovementCenter',
    component: () => import('@/views/movement/MovementCenter.vue'),
  },
  // 跟进节点
  {
    path: '/followup-nodes',
    name: 'FollowupNodeList',
    component: () => import('@/views/task/FollowupNodeList.vue'),
  },
  // 跟进任务
  {
    path: '/followup-tasks',
    name: 'FollowupTaskList',
    component: () => import('@/views/task/FollowupTaskList.vue'),
  },
  {
    path: '/followup-tasks/:id',
    name: 'FollowupTaskDetail',
    component: () => import('@/views/task/FollowupTaskDetail.vue'),
  },
  // 沟通
  {
    path: '/communications/create',
    name: 'CommunicationCreate',
    component: () => import('@/views/communication/CommunicationCreate.vue'),
  },
  {
    path: '/communications/:id',
    name: 'CommunicationDetail',
    component: () => import('@/views/communication/CommunicationDetail.vue'),
  },
  // 试用期评估
  {
    path: '/employments/:employmentId/probation-reviews',
    name: 'ProbationReviewList',
    component: () => import('@/views/probation/ProbationReviewList.vue'),
  },
  {
    path: '/employments/:employmentId/probation-reviews/create',
    name: 'ProbationReviewCreate',
    component: () => import('@/views/probation/ProbationReviewDetail.vue'),
  },
  {
    path: '/probation-reviews/:id',
    name: 'ProbationReviewDetail',
    component: () => import('@/views/probation/ProbationReviewDetail.vue'),
  },
  // 转正
  {
    path: '/employments/:employmentId/regularization',
    name: 'RegularizationView',
    component: () => import('@/views/regularization/RegularizationView.vue'),
  },
  // 离职
  {
    path: '/employments/:employmentId/separation',
    name: 'SeparationView',
    component: () => import('@/views/separation/SeparationView.vue'),
  },
  // 异动
  {
    path: '/employments/:employmentId/changes',
    name: 'ChangeList',
    component: () => import('@/views/change/ChangeList.vue'),
  },
  {
    path: '/employments/:employmentId/changes/create',
    name: 'ChangeCreate',
    component: () => import('@/views/change/ChangeCreate.vue'),
  },
  {
    path: '/employment-changes/:id',
    name: 'ChangeEdit',
    component: () => import('@/views/change/ChangeCreate.vue'),
  },
  // 待办
  {
    path: '/todos',
    name: 'TodoList',
    component: () => import('@/views/todo/TodoList.vue'),
  },
  // 操作日志
  {
    path: '/operation-logs',
    name: 'OperationLogList',
    component: () => import('@/views/log/OperationLogList.vue'),
  },
  // 花名册导入
  {
    path: '/roster-imports',
    name: 'RosterImportList',
    component: () => import('@/views/roster/RosterImportList.vue'),
  },
  {
    path: '/roster-imports/new',
    name: 'RosterImportWizard',
    component: () => import('@/views/roster/RosterImportWizard.vue'),
  },
  {
    path: '/roster-imports/:id',
    name: 'RosterImportDetail',
    component: () => import('@/views/roster/RosterImportDetail.vue'),
  },
  // HR 确认事项
  {
    path: '/hr-confirmations',
    name: 'HrConfirmations',
    component: () => import('@/views/confirmation/ConfirmationList.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
