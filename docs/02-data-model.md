# 02 数据模型

> 版本：v0.4.0  
> 最后更新：2026-07-16  
> 本文件为概念模型，不代表最终 SQL。

## 1. 建模原则

- 员工档案与任职记录分离。
- 任务、沟通、文本版本、AI、风险和人工决策状态分离。
- 历史数据不覆盖。
- 关键业务记录逻辑删除。
- 自动生成逻辑具备唯一业务键。
- SQLite 开启外键约束。
- V1 不建立录音、ASR、转写、登录、会话、角色或权限表。
- 表结构和状态规则以 [01-domain-rules.md](01-domain-rules.md) 为准。

## 2. 通用字段和例外

普通业务表可保留以下审计字段，以兼容现有代码：

- `id`
- `created_at`
- `created_by`
- `updated_at`
- `updated_by`
- `version`
- `is_deleted`
- `deleted_at`
- `deleted_by`

例外：

- `operation_log` 为追加写审计表，不包含更新、版本和逻辑删除字段。
- 单用户模式下，`created_by`、`updated_by`、`deleted_by` 等由后端写入固定操作者，不要求关联用户表。
- 纯关联历史表可以使用 `active`、`removed_at` 表示失效，不物理删除记录。


## 3. 单用户字段兼容策略

- V1 不创建 `user`、`account`、`role`、`permission`、`user_role`、`role_permission`、`session`、`token` 等认证授权表。
- 现有业务字段 `created_by`、`updated_by`、`deleted_by`、`user_id`、`hr_user_id`、`reviewed_by`、`confirmed_by`、`completed_by` 和 `operator_id` 可以保留，避免重构已完成业务代码。
- 后端统一写入配置中的固定本地操作者，默认 `LOCAL_OPERATOR_ID=1`、`LOCAL_OPERATOR_NAME=LOCAL_HR`。
- 客户端不得决定操作者；请求体中的操作者字段应忽略或校验拒绝。
- 上述字段不新增用户表外键。若已有未上线的外键设计，应在迁移中移除外键或改为普通审计字段。
- 若现有代码已经有一条本地操作者记录，可保留作为审计字典，但该记录不得包含密码、登录令牌或角色权限逻辑。
- 参与人、确认和待办表可以保留兼容；单用户模式下 `user_id` 恒为固定本地操作者。

## 4. 关系概览

```text
employee
  └── employment_record
        ├── probation_review
        ├── regularization_record
        ├── employment_change
        ├── separation_record
        ├── followup_task
        │     ├── followup_task_participant
        │     ├── followup_task_confirmation
        │     └── communication_record
        │           ├── communication_text_version
        │           │     └── ai_summary_version
        │           │           └── risk_assessment
        │           └── risk_assessment（纯人工时可不关联 AI）
        └── system_todo

followup_node_definition
  └── followup_task

operation_log 关联全部关键对象
```

## 5. `employee`

推荐字段：

- `id`
- `employee_no`
- `name`
- `normalized_name`
- `mobile`
- `email`
- `source_employee_key`
- `employee_status`
- `source`
- 通用字段

字段说明：

- `source_employee_key`：花名册或外部人员系统提供的来源标识，仅用于追踪和辅助人工核对。
- `source_employee_key` 不保存身份证号码，不作为数据库主键，不作为 V1 自动匹配唯一依据。
- `normalized_name` 仅执行确定性空格标准化，不做拼音或模糊匹配。

约束和规则：

- 不对姓名建立全局唯一约束，因为允许同名员工。
- 导入匹配冲突应进入人工处理流程，不通过数据库约束错误代替业务提示。
- `employee_no` 是否唯一由公司数据质量决定；V1 不以其作为自动合并依据。

## 6. `employment_record`

推荐字段：

- `id`
- `employee_id`
- `employment_seq`
- `employment_status`
- `hire_date`
- `probation_start_date`
- `probation_end_date`
- `probation_status`
- 部门、岗位和负责人引用或快照
- `regularization_date`
- `separation_date`
- `date_rule_source`
- `probation_end_date_source`
- 通用字段

推荐约束：

- 同一员工最多一条 `PENDING`、`ACTIVE` 或 `SEPARATING` 的有效任职记录。
- `employee_id + employment_seq` 唯一。
- 离职日期和转正日期不得早于入职日期。
- 再次入职增加 `employment_seq`，不得覆盖历史任职。

## 7. `followup_node_definition`

推荐字段：

- `id`
- `node_code`
- `node_name`
- `trigger_type`
- `offset_days`
- `enabled`
- `default_assignee_rule`
- `confirmation_mode`
- `node_version`
- `effective_from`
- `effective_to`
- 通用字段

规则：

- `confirmation_mode` 为 `ALL` 或 `ANY`，默认 `ALL`。
- 默认数据初始化必须幂等。
- 节点逻辑删除或停用不影响历史任务。

## 8. `followup_task`

推荐字段：

- `id`
- `employment_id`
- `node_definition_id`
- `node_version`
- `node_code_snapshot`
- `task_name`
- `task_source`
- `trigger_type_snapshot`
- `offset_days_snapshot`
- `planned_date`
- `original_planned_date`
- `date_adjusted_manually`
- `followup_status`
- `confirmation_mode`
- `completed_at`
- `completed_by`
- `cancel_reason`
- `idempotency_key`
- 通用字段

约束和规则：

- 对 `idempotency_key` 建唯一索引。
- 入职日期重算只更新符合条件任务的 `planned_date`，不删除重建任务。
- 节点后续变化不得修改快照字段。

## 9. `followup_task_participant`

推荐字段：

- `id`
- `task_id`
- `user_id`（单用户模式固定为本地操作者）
- `participant_role`
- `active`
- `assigned_at`
- `removed_at`
- `created_by`

推荐唯一约束：同一任务和用户只能有一条当前有效参与记录。

## 10. `followup_task_confirmation`

推荐字段：

- `id`
- `task_id`
- `user_id`（单用户模式固定为本地操作者）
- `confirmation_status`
- `comment`
- `confirmed_at`
- `request_id`
- `created_at`

推荐唯一约束：`task_id + user_id + request_id` 唯一。重复确认必须幂等。

## 11. `communication_record`

用途：保存沟通业务信息、当前文本引用、HR 手工总结和人工结论。

推荐字段：

- `id`
- `employment_id`
- `followup_task_id`
- `communication_type`
- `communication_at`
- `hr_user_id`（单用户模式固定为本地操作者）
- `communication_status`
- `current_text_version_id`
- `current_text_version_no`
- `current_text_hash`
- `manual_summary`
- `hr_conclusion`
- `source`
- 通用字段

规则：

- 当前文本全文存放在 `communication_text_version`。
- 可以在查询模型中冗余当前文本，但数据库权威来源为当前文本版本记录。
- AI 不得写入 `manual_summary` 和 `hr_conclusion`。
- 草稿允许没有文本版本，生成 AI 前必须存在非空当前版本。

## 12. `communication_text_version`

用途：保存每次修改后的完整沟通文本。

推荐字段：

- `id`
- `communication_id`
- `version_no`
- `text_content`
- `text_hash`
- `text_length`
- `change_reason`
- `created_at`
- `created_by`

约束和规则：

- `communication_id + version_no` 唯一。
- 新版本追加写，禁止原地修改旧版本全文。
- `text_hash` 用于一致性校验，不替代全文版本。
- 操作日志引用版本 ID 和哈希，不重复存储全文。

## 13. `ai_summary_version`

推荐字段：

- `id`
- `communication_id`
- `version_no`
- `source_text_version_id`
- `source_text_version_no`
- `source_text_hash`
- `provider`
- `model_name`
- `prompt_version`
- `prompt_snapshot`
- `output_schema_version`
- `summary_status`
- `structured_summary`
- `raw_response_ref`
- `is_ai_suggestion`
- `is_current`
- `is_stale`
- `started_at`
- `finished_at`
- `failure_type`
- `failure_reason`
- `retry_count`
- `idempotency_key`
- 通用字段

规则：

- `communication_id + version_no` 唯一。
- `source_text_version_id` 必须指向同一沟通记录的文本版本。
- 不再使用 `source_text_snapshot`，避免与完整文本版本重复存储。
- 重新生成新增 AI 版本。
- 当前文本版本与来源版本不一致时 `is_stale=true`。
- 历史结果不物理删除。

## 14. `risk_assessment`

推荐字段：

- `id`
- `communication_id`
- `source_text_version_id`
- `ai_summary_version_id`（可空）
- `assessment_source`：`AI` 或 `MANUAL`
- `ai_risk_level`
- `ai_risk_reasons`
- `ai_evidence`
- `ai_followup_suggestions`
- `risk_review_status`
- `hr_risk_level`
- `hr_comment`
- `reviewed_by`
- `reviewed_at`
- `is_current`
- 通用字段

规则：

- AI 结果校验成功时，与 `ai_summary_version` 在同一事务中自动创建。
- AI 记录初始 `risk_review_status=PENDING_REVIEW`。
- 纯人工风险判断允许 `ai_summary_version_id` 为空，`assessment_source=MANUAL`。
- AI 建议和 HR 最终等级必须分开。
- 风险等级使用 `UNSPECIFIED`、`LOW`、`MEDIUM`、`HIGH`。

## 15. `probation_review`

推荐字段：

- `id`
- `employment_id`
- `followup_task_id`
- `communication_id`
- `review_seq`
- `review_stage`：`FOLLOWUP` 或 `FINAL`
- `review_status`
- `hr_evaluation`
- `employee_feedback`
- `recommendation`
- `reviewed_by`
- `reviewed_at`
- 通用字段

规则：

- 同一任职允许多条过程评估和最终评估历史。
- 转正确认前至少存在一条已完成的 `FINAL` 评估。

## 16. `regularization_record`

推荐字段：

- `id`
- `employment_id`
- `probation_review_id`
- `decision`：`APPROVED`、`EXTENDED`、`NOT_APPROVED`
- `effective_date`
- `new_probation_end_date`（延期时使用）
- `decision_reason`
- `ai_summary_version_id`（可空，仅引用）
- `confirmed_by`
- `confirmed_at`
- `is_effective`
- 通用字段

约束：同一任职最多一条当前生效的 `APPROVED` 记录。

## 17. `employment_change`

推荐字段：

- `id`
- `employment_id`
- `change_type`
- `effective_date`
- `before_data`
- `after_data`
- `reason`
- `confirmed_by`
- `confirmed_at`
- 通用字段

V1 的 `change_type` 支持 `DEPARTMENT`、`POSITION`、`MANAGER`。

## 18. `separation_record`

推荐字段：

- `id`
- `employment_id`
- `planned_separation_date`
- `actual_separation_date`
- `separation_type`
- `reason`
- `hr_comment`
- `confirmed_by`
- `confirmed_at`
- 通用字段

离职确认后取消未完成任务，不物理删除相关历史。

## 19. `system_todo`

推荐字段：

- `id`
- `user_id`（单用户模式固定为本地操作者）
- `business_type`
- `business_id`
- `title`
- `due_at`
- `todo_status`
- `priority`
- `source`
- `idempotency_key`
- 通用字段

同一业务对象、本地操作者和待办类型不得重复生成有效待办。

## 20. `operation_log`

推荐字段：

- `id`
- `operator_id`（单用户模式固定为本地操作者）
- `operated_at`
- `object_type`
- `object_id`
- `operation_type`
- `before_data`
- `after_data`
- `operation_source`
- `business_id`
- `request_id`
- `ip_address`
- `user_agent`

日志只追加，不提供修改、逻辑删除或物理删除接口，因此不包含普通通用更新和删除字段。

## 21. 索引建议

至少评估：

- `employee.normalized_name`
- `employee.employee_no`
- `employment_record.employee_id + employment_seq` 唯一
- 当前有效任职记录查询
- `followup_task.employment_id + planned_date`
- `followup_task.idempotency_key` 唯一
- `communication_record.employment_id`
- `communication_record.followup_task_id`
- `communication_text_version.communication_id + version_no` 唯一
- `ai_summary_version.communication_id + version_no` 唯一
- `ai_summary_version.idempotency_key` 唯一或条件唯一
- `risk_assessment.communication_id + is_current`
- `system_todo.user_id + todo_status + due_at`（`user_id` 为固定本地操作者）
- `operation_log.object_type + object_id`

## 22. V1 禁止建立的结构

认证授权类：

- `user_account`
- `role`
- `permission`
- `user_role`
- `role_permission`
- `auth_session`
- `access_token`
- `refresh_token`

音频和 ASR 类：

- `recording`
- `audio_file`
- `transcript`
- `transcript_version`
- `asr_task`
- `asr_provider`
- `asr_provider_config`
- `audio_processing_job`

若旧项目已有这些表，不物理删除历史数据；停止新增、禁用入口，并在删除前提供备份、迁移和回滚方案。

## 23. 迁移要求

任何数据库变更必须说明：

1. 正向迁移。
2. 回滚迁移。
3. 历史数据回填。
4. 空值和默认值。
5. 唯一索引建立前的重复检查。
6. 当前沟通文本如何生成首个完整文本版本。
7. 旧 AI 结果如何关联文本版本。
8. `source_text_snapshot` 历史数据如何迁移或只读保留。
9. 旧 `identity_ref` 如何迁移到 `source_employee_key`，并确认其中不含不应保存的敏感身份证数据。
10. 若已有录音或转写数据，如何只读保留。
11. 若存在未完成的认证授权表、外键或字段，如何停止使用并保持业务数据兼容。
12. 接口兼容方式。

后端统一使用 SQLAlchemy 2.x 同步 ORM，数据库迁移统一使用 Alembic，不得并行引入第二套 ORM 或迁移框架。
