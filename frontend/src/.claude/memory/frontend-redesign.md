---
name: frontend-redesign-completed
description: 员工生命周期系统前端重设计已按文档完成
metadata:
  type: project
---

员工生命周期系统前端重设计已完成。基于 `docs/2026年7月16日-employee-lifecycle-frontend-redesign.md` 文档实施。

**核心变更：**

1. **设计系统建立**：CSS 变量体系 (tokens.css)、重置样式、排版、通用工具类
2. **布局重构**：白色侧栏 232px、顶部工具栏（搜索 + 新增按钮）、可折叠导航
3. **导航重组**：工作/员工/系统 三级分组，根路由从 `/employees` 改为 `/dashboard`
4. **基础组件**：Button、Badge、Input、Select、Modal、Drawer、Toast、Empty、Skeleton
5. **业务组件**：EmployeeAvatar、LifecycleBadge、RiskBadge、ProbationProgress、LifecycleStepper、EmployeeTimeline、ChangeDiffPanel、NextActionCard、EmployeeQuickDrawer、EmployeeIdentityBar
6. **状态映射**：所有后端英文枚举通过 `constants/status.ts` 映射为中文
7. **日期工具**：`utils/date.ts` 统一日期格式化、相对时间、试用期进度计算
8. **新增页面**：Dashboard (工作台)、WorkItemCenter (工作事项)、ProbationCenter (试用期中心)、RegularizationCenter (转正中心)、MovementCenter (异动与离职)
9. **页面重构**：EmployeeList (新列、筛选、预览抽屉)、EmployeeDetail (生命周期轨道、操作卡)、SeparationView (离职流程步骤、危险区域)、RegularizationView (步骤条)、ChangeCreate (前后对比面板)
10. **问题修复**：离职记录的"计划日期"现在展示 `planned_separation_date`、"实际日期"展示 `actual_separation_date`；移除所有 `alert/confirm/prompt` 替换为 Toast 和 BaseModal；移除 ✅/❌ emoji 和英文状态直接显示

**Why:** 将系统从"员工数据管理后台"升级为"HR 每日工作台 + 员工生命周期驾驶舱"

**How to apply:** 后续功能扩展应优先使用现有组件和设计变量，不重复定义基础样式。状态展示应使用 `getStatusLabel()` 系列函数。新增路由需在侧栏的 `AppSidebar.vue` 的 navGroups 中注册。业务组件位于 `src/components/business/`，基础组件位于 `src/components/base/`。
