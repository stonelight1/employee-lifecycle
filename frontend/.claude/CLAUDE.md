# 员工生命周期系统前端

## 技术栈
- Vue 3 + TypeScript + Vite
- Vue Router + Pinia + Axios + Day.js
- 图标: lucide-vue-next
- 无大型 UI 组件库，使用自定义组件体系

## 目录结构
```
src/
├── api/                    # Axios 实例与通用请求函数
├── components/
│   ├── base/               # 基础通用组件 (Button, Badge, Modal, Toast, etc.)
│   ├── business/           # 业务组件 (LifecycleBadge, ProbationProgress, etc.)
│   └── layout/             # 布局组件 (AppLayout, AppSidebar, AppTopbar)
├── composables/            # 组合式函数 (useToast, useConfirm)
├── constants/              # 常量与状态映射 (status.ts)
├── router/                 # 路由定义
├── services/               # 服务层 (dashboardService, workItemService)
├── stores/                 # Pinia 状态管理
├── styles/                 # 全局样式 (tokens.css, reset.css, etc.)
├── types/                  # TypeScript 类型定义
├── utils/                  # 工具函数 (date.ts)
└── views/                  # 页面组件
    ├── dashboard/          # 工作台
    ├── employee/           # 员工中心、员工详情、员工表单
    ├── work/               # 工作事项
    ├── probation/          # 试用期中心、评估
    ├── regularization/     # 转正管理
    ├── movement/           # 异动与离职
    ├── task/               # 跟进任务
    ├── todo/               # 待办事项
    ├── communication/      # 沟通记录
    ├── change/             # 异动表单
    ├── separation/         # 离职流程
    └── log/                # 操作日志
```

## 设计规范

### 颜色
- 主色: `--color-primary: #4F46E5` (禁止使用 `#409EFF`)
- 辅助色: teal / warning / danger / success
- 中性色: bg / surface / text-primary / text-secondary / border

### 状态映射
所有后端英文枚举必须通过 `constants/status.ts` 中的映射函数转为中文展示：
- `getStatusLabel(employmentStatusMap, value)` → 员工状态
- `getStatusLabel(followupStatusMap, value)` → 跟进任务状态
- 其他同理
- 禁止在模板中直接显示 `PENDING`、`ACTIVE` 等英文枚举

### 组件使用规则
- 禁用原生 `alert()`, `confirm()`, `prompt()`
- 使用 `useToast()` 的 `showToast()` 替代 alert
- 使用 `useConfirm()` 的 `confirm()` 替代 confirm
- 使用 BaseModal 替代自定义弹窗
- 禁用 ✅/❌ 作为正式状态控件

### 路由
- 根路径 `/` 重定向到 `/dashboard`
- 导航分组: 工作 / 员工 / 系统
- 现有业务路由保持不动

### 图标
- 统一使用 lucide-vue-next
- 禁止使用 Emoji 和空字符串作为 UI 图标
- 侧栏图标在 AppSidebar.vue 中内联 SVG

### 生命周期阶段颜色
```
PENDING: 紫色     PROBATION: 蓝色
REGULARIZATION_PENDING: 橙色    ACTIVE: 绿色
CHANGING: 紫色    SEPARATING: 红色    SEPARATED: 灰色
```

### 风险颜色
```
HIGH: 深红    MEDIUM: 橙    LOW: 蓝    NONE: 绿
```
