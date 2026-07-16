# 03 API 契约

> 版本：v0.4.0  
> 最后更新：2026-07-16  
> 路径为推荐规范；如已有接口，优先兼容。

## 1. 基本原则

- 资源接口和业务动作接口分离。
- 转正、离职、确认和驳回不得通过通用更新接口静默完成。
- 写接口支持幂等和并发控制。
- 状态流转校验前置状态。
- V1 为单用户模式，接口不执行登录、角色、权限点或数据范围校验。
- 重新生成 AI 总结创建新版本。
- 沟通文本修改创建新的完整文本版本。
- 一次 AI 调用同时产生总结和风险建议。
- 风险审核是独立人工动作，不是第二次 AI 调用。
- V1 不提供录音或 ASR 接口。

## 2. 通用格式

日期使用 `YYYY-MM-DD`。时间使用包含时区的 ISO 8601。

分页参数：

- `page`
- `page_size`
- `sort_by`
- `sort_order`

默认每页 20，最大 100。

成功响应：

```json
{
  "success": true,
  "data": {},
  "request_id": "..."
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "AI_SUMMARY_OUTDATED",
    "message": "沟通文本已修改，请重新生成 AI 建议",
    "details": {}
  },
  "request_id": "..."
}
```

不得返回服务器堆栈、绝对路径、密钥或模型凭证。

## 3. 推荐错误码

| 错误码 | 含义 |
|---|---|
| `VALIDATION_ERROR` | 参数错误 |
| `RESOURCE_NOT_FOUND` | 资源不存在或不可见 |
| `RESOURCE_DELETED` | 资源已逻辑删除 |
| `CONFLICT` | 状态或数据冲突 |
| `DUPLICATE_REQUEST` | 重复请求 |
| `VERSION_CONFLICT` | 并发版本冲突 |
| `INVALID_STATE_TRANSITION` | 非法状态流转 |
| `EMPLOYEE_MATCH_AMBIGUOUS` | 姓名匹配到多个员工，需要人工处理 |
| `ACTIVE_EMPLOYMENT_EXISTS` | 员工已有有效任职记录 |
| `FINAL_PROBATION_REVIEW_REQUIRED` | 缺少已完成的最终试用期评估 |
| `COMMUNICATION_TEXT_REQUIRED` | 沟通文本为空 |
| `COMMUNICATION_TEXT_TOO_LONG` | 沟通文本过长 |
| `AI_NOT_CONFIGURED` | AI 未配置或已关闭 |
| `AI_SUMMARY_PROCESSING` | AI 处理中 |
| `AI_SUMMARY_FAILED` | AI 总结失败 |
| `AI_RESPONSE_INVALID` | AI 返回格式错误 |
| `AI_SUMMARY_OUTDATED` | AI 基于旧文本 |
| `INTERNAL_ERROR` | 未分类错误 |

V1 不定义 ASR、录音或转写错误码。

## 4. 幂等和并发

以下接口接收 `Idempotency-Key` 或 `request_id`：

- 新增和导入员工。
- 创建任职。
- 生成跟进任务。
- 完成或确认任务。
- 创建沟通记录和保存新文本版本。
- 生成或重新生成 AI 建议。
- 审核风险。
- 转正确认。
- 离职确认。

更新接口携带 `version`。条件更新失败返回 `VERSION_CONFLICT`。

## 5. 员工接口

- `GET /api/employees`
- `POST /api/employees`
- `GET /api/employees/{employee_id}`
- `PATCH /api/employees/{employee_id}`
- `DELETE /api/employees/{employee_id}`
- `GET /api/employees/{employee_id}/timeline`

要求：

- 删除为逻辑删除。
- 普通列表不返回完整沟通文本、AI 总结或风险依据。
- 导入按姓名匹配出现多匹配时返回 `EMPLOYEE_MATCH_AMBIGUOUS` 和候选项，不得自动合并。

## 6. 任职接口

- `POST /api/employees/{employee_id}/employments`
- `GET /api/employees/{employee_id}/employments`
- `GET /api/employments/{employment_id}`
- `PATCH /api/employments/{employment_id}`
- `POST /api/employments/{employment_id}/date-change-preview`
- `POST /api/employments/{employment_id}/date-change-confirm`
- `POST /api/employments/{employment_id}/recalculate-followups`
- `POST /api/employments/{employment_id}/regularization-preview`
- `POST /api/employments/{employment_id}/regularize`
- `POST /api/employments/{employment_id}/start-separation`
- `POST /api/employments/{employment_id}/confirm-separation`

日期修改预览必须返回：

- 旧入职日期和新入职日期。
- 自动重算任务及其新旧计划日期。
- 已完成任务。
- 处理中和待确认任务。
- 人工调期任务。
- 人工创建任务。
- 试用期结束日期变化。
- 不修改原因。

确认前不修改数据库。确认时只更新符合规则的现有任务，不删除后重建。

## 7. 跟进节点接口

- `GET /api/followup-nodes`
- `POST /api/followup-nodes`
- `GET /api/followup-nodes/{node_id}`
- `PATCH /api/followup-nodes/{node_id}`
- `POST /api/followup-nodes/{node_id}/enable`
- `POST /api/followup-nodes/{node_id}/disable`
- `DELETE /api/followup-nodes/{node_id}`

要求：

- 删除为逻辑删除。
- `confirmation_mode` 仅允许 `ALL` 或 `ANY`，默认 `ALL`。
- 节点修改不得覆盖已生成任务的规则快照。
- 停用或删除节点不自动取消历史任务。

## 8. 跟进任务接口

- `GET /api/followup-tasks`
- `POST /api/followup-tasks`
- `GET /api/followup-tasks/{task_id}`
- `PATCH /api/followup-tasks/{task_id}`
- `POST /api/followup-tasks/{task_id}/start`
- `POST /api/followup-tasks/{task_id}/submit`
- `POST /api/followup-tasks/{task_id}/confirm`
- `POST /api/followup-tasks/{task_id}/reject`
- `POST /api/followup-tasks/{task_id}/cancel`
- `POST /api/followup-tasks/{task_id}/participants`
- `DELETE /api/followup-tasks/{task_id}/participants/{user_id}`

服务端根据当前状态、有效确认人、确认模式快照和确认记录计算任务是否完成。V1 不支持撤回确认。

## 9. 沟通记录和文本版本接口

- `GET /api/communications`
- `POST /api/communications`
- `GET /api/communications/{communication_id}`
- `PATCH /api/communications/{communication_id}`
- `DELETE /api/communications/{communication_id}`
- `GET /api/communications/{communication_id}/text-versions`
- `GET /api/communications/{communication_id}/text-versions/{version_no}`

创建或修改请求示例：

```json
{
  "employment_id": 123,
  "followup_task_id": 456,
  "communication_type": "PROBATION_FOLLOWUP",
  "communication_at": "2026-07-15T10:00:00+08:00",
  "communication_text": "HR 手工输入或粘贴的沟通内容",
  "manual_summary": "HR 手工总结",
  "hr_conclusion": "HR 人工结论",
  "version": 1
}
```

响应至少包含：

- `current_text_version_id`
- `current_text_version_no`
- `current_text_hash`
- 当前 AI 版本。
- `ai_summary_is_stale`。
- HR 手工总结与结论。
- AI 建议单独字段。

修改规则：

- 文本变化时追加新的完整文本版本。
- 不允许原地修改历史版本。
- 旧 AI 结果标记过期。
- 不自动调用 AI。
- 删除为逻辑删除。

## 10. AI 总结和风险生成接口

- `POST /api/communications/{communication_id}/ai-summaries`
- `POST /api/communications/{communication_id}/regenerate-ai-summary`
- `GET /api/communications/{communication_id}/ai-summaries`
- `GET /api/ai-summaries/{summary_id}`
- `POST /api/ai-summaries/{summary_id}/select-current`

请求示例：

```json
{
  "source_text_version_id": 321,
  "request_id": "client-generated-id"
}
```

处理规则：

1. 沟通文本不能为空。
2. 请求文本版本必须是当前文本版本。
3. 同一文本版本处理中重复请求返回已有执行。
4. 一次模型调用同时生成总结和风险建议。
5. 返回结构必须整体校验。
6. 校验成功后，在同一事务中创建 `ai_summary_version` 和 `risk_assessment`。
7. 风险记录初始状态为 `PENDING_REVIEW`。
8. 任一部分校验失败时整体失败，不保存半份成功数据。
9. 重新生成创建新版本。
10. AI 不得覆盖 HR 人工总结、风险或结论。

响应示例：

```json
{
  "summary_id": 789,
  "risk_assessment_id": 790,
  "summary_status": "SUCCEEDED",
  "source_text_version_id": 321,
  "current_text_version_id": 322,
  "is_stale": true,
  "is_ai_suggestion": true,
  "risk_review_status": "PENDING_REVIEW"
}
```

## 11. 风险审核和人工风险接口

AI 风险审核：

- `GET /api/communications/{communication_id}/risk-assessments`
- `GET /api/risk-assessments/{risk_id}`
- `POST /api/risk-assessments/{risk_id}/confirm`
- `POST /api/risk-assessments/{risk_id}/modify`
- `POST /api/risk-assessments/{risk_id}/reject`

纯人工风险：

- `PUT /api/communications/{communication_id}/manual-risk-assessment`

规则：

- 风险等级仅允许 `UNSPECIFIED`、`LOW`、`MEDIUM`、`HIGH`。
- 所有审核动作记录固定本地操作者、时间、前后数据和意见。
- 来源 AI 结果过期时，阻止直接确认旧 AI 建议；允许 HR 保存独立人工判断。
- 人工风险记录允许不关联 AI 总结版本。

## 12. 试用期评估和转正接口

试用期评估：

- `GET /api/employments/{employment_id}/probation-reviews`
- `POST /api/employments/{employment_id}/probation-reviews`
- `GET /api/probation-reviews/{review_id}`
- `PATCH /api/probation-reviews/{review_id}`
- `POST /api/probation-reviews/{review_id}/complete`

转正：

- `POST /api/employments/{employment_id}/regularization-preview`
- `POST /api/employments/{employment_id}/regularize`
- `GET /api/employments/{employment_id}/regularization-records`

转正确认前必须存在已完成的 `FINAL` 评估，否则返回 `FINAL_PROBATION_REVIEW_REQUIRED`。

`decision` 仅允许 `APPROVED`、`EXTENDED`、`NOT_APPROVED`。`NOT_APPROVED` 不自动发起离职。

## 13. 异动和离职接口

异动：

- `GET /api/employments/{employment_id}/changes`
- `POST /api/employments/{employment_id}/changes`
- `GET /api/employment-changes/{change_id}`
- `PATCH /api/employment-changes/{change_id}`

离职：

- `POST /api/employments/{employment_id}/separation-preview`
- `POST /api/employments/{employment_id}/start-separation`
- `POST /api/employments/{employment_id}/confirm-separation`
- `GET /api/employments/{employment_id}/separation-records`

离职确认在同一事务中：

- 创建离职记录。
- 更新任职状态和离职日期。
- 取消未完成任务和待办。
- 保留已完成任务、沟通、AI、风险和日志。

## 14. 待办和日志接口

待办：

- `GET /api/todos`
- `GET /api/todos/{todo_id}`
- `POST /api/todos/{todo_id}/complete`
- `POST /api/todos/{todo_id}/cancel`

日志：

- `GET /api/operation-logs`
- `GET /api/operation-logs/{log_id}`

待办完成不得绕过对应业务规则。日志不提供修改和删除接口。

## 15. V1 不提供的接口

不得实现：

- `/recordings`
- `/audio`
- `/transcriptions`
- `/transcripts`
- `/retranscribe`
- `/asr`
- ASR 厂商配置接口
- 音频上传、播放和下载接口

若旧接口存在，先确认调用方和历史数据，再选择禁用、兼容返回或删除。

## 16. 单用户访问与兼容

- 所有业务接口不要求 `Authorization`、Cookie Session、JWT 或其他登录凭证。
- 前端不调用登录、刷新令牌、退出、用户信息、角色和权限接口。
- 后端不返回 401 或 403；业务资源不存在或已删除时按 404 或对应业务错误处理。
- API 仍必须校验参数、业务对象关系、状态流转、版本、幂等和逻辑删除，去掉认证不等于去掉业务校验。
- 创建人、修改人、确认人、审核人和日志操作者由后端固定注入，不允许客户端伪造。
- 若旧代码存在可选认证中间件、路由依赖或前端守卫，应移除调用链和页面跳转，不保留“默认放行”的假权限实现。
- 若旧数据库已有用户、角色或权限数据，不作为业务接口前置条件；删除前必须备份，优先停止使用而不是直接破坏历史数据。
- 新增字段尽量向后兼容；删除旧字段或接口必须提供迁移和回滚。
- 应用不得直接暴露到公网。访问安全规则参见 [04-permission-rules.md](04-permission-rules.md)。
