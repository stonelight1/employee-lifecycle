"""
自动为所有 SQLAlchemy 模型文件添加 column comment。
运行方式: python scripts/add_column_comments.py
"""
import ast
import os
import re
import sys
from pathlib import Path

# 表 -> 列 -> 注释映射
COLUMN_COMMENTS = {
    # ========== 通用字段 ==========
    "id": "主键ID，自增",
    "created_at": "创建时间",
    "created_by": "创建人",
    "updated_at": "最后更新时间",
    "updated_by": "最后更新人",
    "version": "乐观锁版本号",
    "is_deleted": "逻辑删除标记，0=未删除 1=已删除",
    "deleted_at": "删除时间",
    "deleted_by": "删除人",

    # ========== employee ==========
    "employee.employee_no": "员工工号",
    "employee.name": "姓名",
    "employee.normalized_name": "标准化姓名（去空格转大写，用于匹配与去重）",
    "employee.mobile": "手机号",
    "employee.email": "电子邮箱",
    "employee.source_employee_key": "外部来源系统中的员工唯一标识",
    "employee.employee_status": "员工状态：ACTIVE-在职 INACTIVE-离职 ENTRY_ERROR-入职异常",
    "employee.source": "数据来源描述",
    "employee.profile_completeness_status": "档案完整度：COMPLETE-完整 INCOMPLETE-不完整",

    # ========== employment_record ==========
    "employment_record.employee_id": "员工ID，关联employee表",
    "employment_record.employment_seq": "任职序号，同一员工从1开始递增",
    "employment_record.employment_status": "任职状态：PENDING-待入职 ACTIVE-在职 SEPARATING-离职中 SEPARATED-已离职 CANCELLED-已取消",
    "employment_record.hire_date": "入职日期（兼容旧数据，建议使用expected/actual_hire_date）",
    "employment_record.expected_hire_date": "预计入职日期",
    "employment_record.actual_hire_date": "实际入职日期",
    "employment_record.probation_months": "试用期月数，默认3个月",
    "employment_record.probation_start_date": "试用期开始日期",
    "employment_record.probation_end_date": "试用期结束日期",
    "employment_record.probation_status": "试用期状态：NOT_STARTED-未开始 PROBATION-试用中 REGULARIZED-已转正 EXTENDED-已延长",
    "employment_record.expected_regularization_date": "预计转正日期",
    "employment_record.actual_regularization_date": "实际转正日期",
    "employment_record.regularization_date": "转正日期（兼容旧数据）",
    "employment_record.employment_type": "用工类型：FORMAL-正式 PROBATION-试用 INTERN-实习 CASUAL-兼职",
    "employment_record.work_city": "工作城市",
    "employment_record.work_mode": "工作模式：OFFICE-办公室 REMOTE-远程 HYBRID-混合 UNKNOWN-未知",
    "employment_record.team_name": "团队/组名称",
    "employment_record.department": "所属部门",
    "employment_record.position": "职位名称",
    "employment_record.manager_name": "直属上级姓名",
    "employment_record.separation_date": "离职日期",
    "employment_record.status_before_separating": "离职前的任职状态快照",
    "employment_record.hire_cancelled_at": "入职取消时间",
    "employment_record.hire_cancel_reasons_json": "入职取消原因列表（JSON数组）",
    "employment_record.hire_cancel_note": "入职取消备注说明",
    "employment_record.date_rule_source": "日期规则来源：IMPORT-导入 MANUAL-手动录入",
    "employment_record.probation_end_date_source": "试用期结束日期来源：COMPUTED-自动计算 IMPORT-导入 SPECIFIED-指定",

    # ========== employee_profile ==========
    "employee_profile.employee_id": "员工ID，关联employee表（唯一）",
    "employee_profile.identity_card": "身份证号码",
    "employee_profile.gender": "性别：MALE-男 FEMALE-女",
    "employee_profile.birth_date": "出生日期",
    "employee_profile.household_registration": "户籍地址",
    "employee_profile.residence_address": "现居住地址",
    "employee_profile.household_type": "户籍类型：URBAN-城镇 RURAL-农村",
    "employee_profile.graduation_school": "毕业院校",
    "employee_profile.major": "所学专业",
    "employee_profile.education_level": "最高学历：ASSOCIATE-大专 BACHELOR-本科 MASTER-硕士 DOCTOR-博士",
    "employee_profile.social_insurance_policy": "社保缴纳政策描述",
    "employee_profile.housing_fund_policy": "公积金缴纳政策描述",
    "employee_profile.social_insurance_status": "社保缴纳状态描述",
    "employee_profile.housing_fund_status": "公积金缴纳状态描述",
    "employee_profile.social_insurance_start_date": "社保开始缴纳日期",
    "employee_profile.housing_fund_start_date": "公积金开始缴纳日期",
    "employee_profile.benefit_raw_text": "福利信息原始文本（来自花名册导入）",

    # ========== compensation_record ==========
    "compensation_record.employee_id": "员工ID，关联employee表",
    "compensation_record.employment_id": "任职记录ID，关联employment_record表",
    "compensation_record.raw_salary_text": "原始薪资文本（来自花名册）",
    "compensation_record.salary_type": "薪资类型：MONTHLY-月薪 DAILY-日薪 HOURLY-时薪 UNKNOWN-未知",
    "compensation_record.base_salary": "基本工资金额",
    "compensation_record.probation_salary": "试用期工资金额",
    "compensation_record.regular_salary": "转正后工资金额",
    "compensation_record.daily_rate": "日薪金额",
    "compensation_record.performance_amount": "绩效工资金额",
    "compensation_record.performance_ratio": "绩效比例，如0.1表示10%",
    "compensation_record.commission_text": "提成/佣金说明",
    "compensation_record.other_text": "其他薪资相关说明",
    "compensation_record.effective_date": "薪酬生效日期",
    "compensation_record.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "compensation_record.import_batch_id": "导入批次ID，关联roster_import_batch表",

    # ========== employment_contract ==========
    "employment_contract.employee_id": "员工ID，关联employee表",
    "employment_contract.employment_id": "任职记录ID，关联employment_record表",
    "employment_contract.contract_status": "合同状态：ACTIVE-生效 EXPIRED-到期 TERMINATED-终止",
    "employment_contract.signing_company": "合同签约公司（甲方）",
    "employment_contract.contract_type": "合同类型：FIXED-固定期限 PERMANENT-无固定期限 PROJECT-项目合同 UNKNOWN-未知",
    "employment_contract.start_date": "合同开始日期",
    "employment_contract.end_date": "合同结束日期",
    "employment_contract.signing_sequence": "合同签署序号（第几次签约）",
    "employment_contract.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "employment_contract.confirmed_at": "合同确认时间",

    # ========== employee_financial_account ==========
    "employee_financial_account.employee_id": "员工ID，关联employee表",
    "employee_financial_account.account_type": "账户类型：BANK-银行卡 ALIPAY-支付宝 WECHAT-微信支付",
    "employee_financial_account.account_no": "银行账号/支付账户号",
    "employee_financial_account.bank_name": "开户银行名称",
    "employee_financial_account.is_primary": "是否为主账户",
    "employee_financial_account.account_status": "账户状态：ACTIVE-有效 INACTIVE-停用",
    "employee_financial_account.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "employee_financial_account.confirmed_at": "账户确认时间",

    # ========== employee_assessment ==========
    "employee_assessment.employee_id": "员工ID，关联employee表",
    "employee_assessment.assessment_type": "考核类型：INTERVIEW-面试 PROBATION-试用期 ANNUAL-年度",
    "employee_assessment.result_text": "考核结果文本内容",
    "employee_assessment.attachment_path": "考核附件文件路径",
    "employee_assessment.assessment_date": "考核日期",
    "employee_assessment.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "employee_assessment.import_batch_id": "导入批次ID，关联roster_import_batch表",

    # ========== employee_note ==========
    "employee_note.employee_id": "员工ID，关联employee表",
    "employee_note.employment_id": "任职记录ID，关联employment_record表",
    "employee_note.content": "备注内容",
    "employee_note.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "employee_note.source_id": "来源系统中的原始ID",
    "employee_note.import_batch_id": "导入批次ID，关联roster_import_batch表",
    "employee_note.source_row_no": "来源文件中的行号",
    "employee_note.content_hash": "备注内容SHA256哈希，用于去重",

    # ========== employee_attribute_history ==========
    "employee_attribute_history.employee_id": "员工ID，关联employee表",
    "employee_attribute_history.employment_id": "任职记录ID，关联employment_record表",
    "employee_attribute_history.category": "属性分类（如EMPLOYMENT/CONTACT/PROFILE）",
    "employee_attribute_history.field_name": "发生变更的字段名",
    "employee_attribute_history.before_value_json": "变更前值（JSON格式）",
    "employee_attribute_history.after_value_json": "变更后值（JSON格式）",
    "employee_attribute_history.effective_date": "变更生效日期",
    "employee_attribute_history.source_type": "数据来源类型：IMPORT-导入 MANUAL-手工",
    "employee_attribute_history.source_id": "来源系统中的原始ID",
    "employee_attribute_history.import_batch_id": "导入批次ID，关联roster_import_batch表",
    "employee_attribute_history.operator_name": "操作人姓名",

    # ========== communication_record ==========
    "communication_record.employment_id": "任职记录ID，关联employment_record表",
    "communication_record.followup_task_id": "关联的跟进任务ID",
    "communication_record.communication_type": "沟通类型：PHONE-电话 FACE_TO_FACE-面谈 VIDEO-视频",
    "communication_record.communication_at": "沟通发生时间",
    "communication_record.hr_user_id": "执行沟通的HR用户ID",
    "communication_record.communication_status": "沟通记录状态：DRAFT-草稿 FINALIZED-已完成",
    "communication_record.current_text_version_id": "当前沟通文本版本ID",
    "communication_record.current_text_version_no": "当前沟通文本版本号",
    "communication_record.current_text_hash": "当前沟通文本内容哈希",
    "communication_record.manual_summary": "HR手动撰写的沟通摘要",
    "communication_record.hr_conclusion": "HR沟通结论",
    "communication_record.source": "沟通来源：SYSTEM-系统 AUTO-自动 CREATED-手动创建",

    # ========== communication_text_version ==========
    "communication_text_version.communication_id": "沟通记录ID，关联communication_record表",
    "communication_text_version.version_no": "版本号，从1开始递增",
    "communication_text_version.text_content": "沟通文本内容",
    "communication_text_version.text_hash": "文本内容SHA256哈希",
    "communication_text_version.text_length": "文本字符长度",
    "communication_text_version.change_reason": "变更原因说明",

    # ========== ai_summary_version ==========
    "ai_summary_version.communication_id": "沟通记录ID，关联communication_record表",
    "ai_summary_version.version_no": "AI摘要版本号",
    "ai_summary_version.source_text_version_id": "源文本版本ID",
    "ai_summary_version.source_text_version_no": "源文本版本号",
    "ai_summary_version.source_text_hash": "源文本哈希值",
    "ai_summary_version.provider": "AI服务提供商（如openai/anthropic）",
    "ai_summary_version.model_name": "AI模型名称（如gpt-4/claude-opus-4）",
    "ai_summary_version.prompt_version": "使用的提示词版本号",
    "ai_summary_version.prompt_snapshot": "提示词内容快照",
    "ai_summary_version.output_schema_version": "输出JSON Schema版本号",
    "ai_summary_version.summary_status": "摘要生成状态：PROCESSING-处理中 SUCCESS-成功 FAILED-失败",
    "ai_summary_version.structured_summary": "结构化的AI摘要内容（JSON）",
    "ai_summary_version.raw_response_ref": "AI原始响应引用路径或标识",
    "ai_summary_version.is_ai_suggestion": "是否为AI建议（未被人工确认）",
    "ai_summary_version.is_current": "是否为当前生效版本",
    "ai_summary_version.is_stale": "是否因文本更新而过期",
    "ai_summary_version.started_at": "AI调用开始时间",
    "ai_summary_version.finished_at": "AI调用完成时间",
    "ai_summary_version.failure_type": "失败类型（如TIMEOUT/INVALID_RESPONSE）",
    "ai_summary_version.failure_reason": "失败原因描述",
    "ai_summary_version.retry_count": "已重试次数",
    "ai_summary_version.idempotency_key": "幂等键，保证同一请求不会重复处理",

    # ========== risk_assessment ==========
    "risk_assessment.communication_id": "沟通记录ID，关联communication_record表",
    "risk_assessment.source_text_version_id": "风险评估依据的文本版本ID",
    "risk_assessment.ai_summary_version_id": "使用的AI摘要版本ID，关联ai_summary_version表",
    "risk_assessment.assessment_source": "评估来源：AI-自动评估 HR-人工评估",
    "risk_assessment.ai_risk_level": "AI判断的风险等级：HIGH-高 MEDIUM-中 LOW-低 UNSPECIFIED-未指定",
    "risk_assessment.ai_risk_reasons": "AI判断风险的原因说明",
    "risk_assessment.ai_evidence": "AI引用的风险证据文本",
    "risk_assessment.ai_followup_suggestions": "AI建议的跟进措施",
    "risk_assessment.risk_review_status": "风险审核状态：PENDING_REVIEW-待审核 REVIEWED-已审核",
    "risk_assessment.hr_risk_level": "HR认定风险等级",
    "risk_assessment.hr_comment": "HR评审意见",
    "risk_assessment.reviewed_by": "审核人用户ID",
    "risk_assessment.reviewed_at": "审核时间",
    "risk_assessment.is_current": "是否为当前有效的风险评估",

    # ========== probation_review ==========
    "probation_review.employment_id": "任职记录ID，关联employment_record表",
    "probation_review.followup_task_id": "关联的跟进任务ID",
    "probation_review.communication_id": "关联的沟通记录ID",
    "probation_review.review_seq": "试用期评审序号",
    "probation_review.review_stage": "评审阶段：FOLLOWUP-跟进评审 FINAL-终期评审",
    "probation_review.review_status": "评审状态：PENDING-待评审 COMPLETED-已完成 SKIPPED-已跳过",
    "probation_review.hr_evaluation": "HR评价内容",
    "probation_review.employee_feedback": "员工反馈内容",
    "probation_review.recommendation": "评审建议（如建议转正/延长/解除）",
    "probation_review.reviewed_by": "评审人用户ID",
    "probation_review.reviewed_at": "评审完成时间",

    # ========== regularization_record ==========
    "regularization_record.employment_id": "任职记录ID，关联employment_record表",
    "regularization_record.probation_review_id": "关联的试用期评审ID",
    "regularization_record.decision": "转正决定：APPROVED-通过 EXTENDED-延长 NOT_APPROVED-不通过",
    "regularization_record.effective_date": "转正生效日期",
    "regularization_record.new_probation_end_date": "延长后的新试用期结束日期",
    "regularization_record.decision_reason": "转正决定的原因说明",
    "regularization_record.ai_summary_version_id": "使用的AI摘要版本ID",
    "regularization_record.confirmed_by": "确认人用户ID",
    "regularization_record.confirmed_at": "确认时间",
    "regularization_record.is_effective": "是否已生效，默认TRUE",

    # ========== employment_change ==========
    "employment_change.employment_id": "任职记录ID，关联employment_record表",
    "employment_change.change_type": "变更类型：DEPARTMENT-部门变更 POSITION-职位变更 MANAGER-上级变更",
    "employment_change.effective_date": "变更生效日期",
    "employment_change.before_data": "变更前数据快照（JSON）",
    "employment_change.after_data": "变更后数据快照（JSON）",
    "employment_change.reason": "变更原因",
    "employment_change.confirmed_by": "确认人用户ID",
    "employment_change.confirmed_at": "确认时间",

    # ========== separation_record ==========
    "separation_record.employment_id": "任职记录ID，关联employment_record表",
    "separation_record.planned_separation_date": "计划离职日期",
    "separation_record.actual_separation_date": "实际离职日期",
    "separation_record.separation_type": "离职类型：RESIGNATION-主动辞职 TERMINATION-公司解除 RETIREMENT-退休",
    "separation_record.reason": "离职原因说明",
    "separation_record.hr_comment": "HR备注意见",
    "separation_record.confirmed_by": "确认人用户ID",
    "separation_record.confirmed_at": "确认时间",

    # ========== separation_checklist_item ==========
    "separation_checklist_item.separation_record_id": "离职记录ID，关联separation_record表",
    "separation_checklist_item.item_type": "清单项类型：ASSET_RETURN-资产归还 SYSTEM_LOGOFF-系统注销 DOCUMENT-文档",
    "separation_checklist_item.title": "清单项标题",
    "separation_checklist_item.completed": "是否已完成，默认FALSE",
    "separation_checklist_item.completed_at": "完成时间",
    "separation_checklist_item.remark": "备注说明",

    # ========== followup_node_definition ==========
    "followup_node_definition.node_code": "节点编码，唯一标识",
    "followup_node_definition.node_name": "节点名称",
    "followup_node_definition.trigger_type": "触发类型：DAYS_AFTER_HIRE-入职后天数 DAYS_AFTER_REGULAR-转正后天数",
    "followup_node_definition.offset_days": "相对于触发事件的天数偏移",
    "followup_node_definition.enabled": "是否启用，默认TRUE",
    "followup_node_definition.default_assignee_rule": "默认负责人分配规则",
    "followup_node_definition.confirmation_mode": "确认模式：ALL-全部确认 ANY-任一确认即可",
    "followup_node_definition.node_version": "节点定义版本号",
    "followup_node_definition.effective_from": "生效开始日期",
    "followup_node_definition.effective_to": "生效结束日期",

    # ========== followup_task ==========
    "followup_task.employment_id": "任职记录ID，关联employment_record表",
    "followup_task.node_definition_id": "关联的节点定义ID",
    "followup_task.node_version": "生成任务时节点定义的版本快照",
    "followup_task.node_code_snapshot": "节点编码快照",
    "followup_task.task_name": "任务名称",
    "followup_task.task_source": "任务来源：AUTO-自动创建 MANUAL-手动创建",
    "followup_task.trigger_type_snapshot": "触发类型快照",
    "followup_task.offset_days_snapshot": "偏移天数快照",
    "followup_task.planned_date": "计划执行日期",
    "followup_task.original_planned_date": "原始计划日期（手动调整前）",
    "followup_task.date_adjusted_manually": "计划日期是否被手动调整过",
    "followup_task.followup_status": "任务状态：PENDING-待处理 IN_PROGRESS-进行中 COMPLETED-已完成 CANCELLED-已取消",
    "followup_task.confirmation_mode": "确认模式快照：ALL-全部确认 ANY-任一确认",
    "followup_task.completed_at": "任务完成时间",
    "followup_task.completed_by": "任务完成人用户ID",
    "followup_task.cancel_reason": "取消原因",
    "followup_task.idempotency_key": "幂等键，防止重复创建",

    # ========== followup_task_participant ==========
    "followup_task_participant.task_id": "任务ID，关联followup_task表",
    "followup_task_participant.user_id": "参与者用户ID",
    "followup_task_participant.participant_role": "参与角色：RESPONSIBLE-负责人 PARTICIPANT-参与人 OBSERVER-观察者",
    "followup_task_participant.active": "是否活跃参与者，默认TRUE",
    "followup_task_participant.assigned_at": "分配时间",
    "followup_task_participant.removed_at": "移除时间",
    "followup_task_participant.created_by": "创建人",

    # ========== followup_task_confirmation ==========
    "followup_task_confirmation.task_id": "任务ID，关联followup_task表",
    "followup_task_confirmation.user_id": "确认人用户ID",
    "followup_task_confirmation.confirmation_status": "确认状态：PENDING-待确认 CONFIRMED-已确认 REJECTED-已拒绝",
    "followup_task_confirmation.comment": "确认意见",
    "followup_task_confirmation.confirmed_at": "确认时间",
    "followup_task_confirmation.request_id": "确认请求标识",
    "followup_task_confirmation.created_at": "创建时间",

    # ========== system_todo ==========
    "system_todo.user_id": "待办所属用户ID",
    "system_todo.business_type": "业务类型，如REGULARIZATION_REVIEW/SEPARATION_CHECK",
    "system_todo.business_id": "业务记录ID",
    "system_todo.title": "待办事项标题",
    "system_todo.due_at": "截止日期",
    "system_todo.todo_status": "待办状态：PENDING-待处理 COMPLETED-已完成 CANCELLED-已取消",
    "system_todo.priority": "优先级：HIGH-高 MEDIUM-中 LOW-低",
    "system_todo.source": "待办来源描述",
    "system_todo.idempotency_key": "幂等键，防止重复创建",

    # ========== operation_log ==========
    "operation_log.operator_id": "操作人用户ID",
    "operation_log.operated_at": "操作时间",
    "operation_log.object_type": "操作对象类型（表名/实体名）",
    "operation_log.object_id": "操作对象的主键ID",
    "operation_log.operation_type": "操作类型：CREATE-创建 UPDATE-更新 DELETE-删除",
    "operation_log.before_data": "操作前数据快照（JSON）",
    "operation_log.after_data": "操作后数据快照（JSON）",
    "operation_log.operation_source": "操作来源描述",
    "operation_log.business_id": "业务记录ID，用于关联查询",
    "operation_log.request_id": "请求追踪ID，用于关联同一请求的多个操作",
    "operation_log.ip_address": "操作人IP地址",
    "operation_log.user_agent": "操作人User-Agent",

    # ========== organization_reference ==========
    "organization_reference.reference_type": "参考数据类型：DEPARTMENT-部门 POSITION-职位",
    "organization_reference.name": "名称",
    "organization_reference.normalized_name": "标准化名称（去空格转大写，用于匹配）",
    "organization_reference.enabled": "是否启用，默认TRUE",

    # ========== roster_import_batch ==========
    "roster_import_batch.batch_no": "导入批次号，唯一",
    "roster_import_batch.mode": "导入模式：SYNC-同步导入 ASYNC-异步导入",
    "roster_import_batch.file_name": "上传的原始文件名",
    "roster_import_batch.stored_file_path": "文件存储路径",
    "roster_import_batch.file_sha256": "文件SHA256哈希值，用于去重",
    "roster_import_batch.file_size": "文件大小（字节）",
    "roster_import_batch.sheet_name": "工作表名称（Excel多sheet时）",
    "roster_import_batch.header_row": "表头行内容（JSON数组）",
    "roster_import_batch.header_row_index": "表头所在行号（0-based）",
    "roster_import_batch.column_mappings_json": "列映射配置（JSON），存储表头到字段的映射关系",
    "roster_import_batch.batch_status": "批次状态：UPLOADED-已上传 PARSED-已解析 REVIEWING-审核中 IMPORTED-已导入 FAILED-失败 ROLLED_BACK-已回滚",
    "roster_import_batch.total_rows": "总行数",
    "roster_import_batch.new_count": "新增员工数",
    "roster_import_batch.update_count": "更新员工数",
    "roster_import_batch.unchanged_count": "无变化行数",
    "roster_import_batch.confirmation_count": "需人工确认数",
    "roster_import_batch.warning_count": "警告数",
    "roster_import_batch.error_count": "错误数",
    "roster_import_batch.skipped_count": "跳过行数（如合作地区）",
    "roster_import_batch.imported_count": "实际导入行数",
    "roster_import_batch.started_at": "处理开始时间",
    "roster_import_batch.completed_at": "处理完成时间",
    "roster_import_batch.failed_at": "失败时间",
    "roster_import_batch.failure_message": "失败原因",
    "roster_import_batch.rolled_back_at": "回滚时间",

    # ========== roster_import_row ==========
    "roster_import_row.batch_id": "导入批次ID，关联roster_import_batch表",
    "roster_import_row.row_no": "行号（从1开始）",
    "roster_import_row.employee_id": "匹配到的员工ID（新增时为NULL）",
    "roster_import_row.normalized_name": "标准化后的员工姓名",
    "roster_import_row.match_type": "匹配方式：NEW-新建 MATCH-匹配到已有员工",
    "roster_import_row.row_status": "行处理状态：NEW-待处理 MATCHED-已匹配 REVIEWING-审核中",
    "roster_import_row.import_action": "导入动作：CREATE-新增 UPDATE-更新 SKIP-跳过",
    "roster_import_row.review_status": "审核状态：PENDING-待审核 APPROVED-已通过 REJECTED-已驳回",
    "roster_import_row.execution_status": "执行状态：PENDING-待执行 SUCCESS-成功 FAILED-失败",
    "roster_import_row.lifecycle_decision_json": "生命周期决策（JSON）",
    "roster_import_row.raw_data_json": "原始行数据（JSON，按表头键值对）",
    "roster_import_row.normalized_data_json": "标准化后的行数据（JSON）",
    "roster_import_row.diff_json": "与现有数据的差异对比（JSON）",
    "roster_import_row.planned_actions_json": "计划执行的操作列表（JSON）",
    "roster_import_row.result_json": "执行结果（JSON）",

    # ========== roster_import_issue ==========
    "roster_import_issue.batch_id": "导入批次ID，关联roster_import_batch表",
    "roster_import_issue.row_id": "关联行ID，关联roster_import_row表",
    "roster_import_issue.employee_id": "关联员工ID",
    "roster_import_issue.field_key": "引起问题的字段标识",
    "roster_import_issue.issue_code": "问题编码，用于前端i18n和分类处理",
    "roster_import_issue.severity": "严重程度：ERROR-错误 WARNING-警告 INFO-提示",
    "roster_import_issue.title": "问题标题",
    "roster_import_issue.message": "问题详细描述",
    "roster_import_issue.old_value_json": "原始值（JSON）",
    "roster_import_issue.new_value_json": "新值（JSON）",
    "roster_import_issue.allowed_actions_json": "允许的解决操作列表（JSON）",
    "roster_import_issue.resolution_status": "解决状态：PENDING-待处理 RESOLVED-已解决 DISMISSED-已忽略",
    "roster_import_issue.resolution_action": "解决时执行的操作",
    "roster_import_issue.resolution_value_json": "解决后的值（JSON）",
    "roster_import_issue.resolution_note": "解决备注",
    "roster_import_issue.resolved_at": "解决时间",

    # ========== roster_import_operation ==========
    "roster_import_operation.batch_id": "导入批次ID，关联roster_import_batch表",
    "roster_import_operation.row_id": "关联行ID，关联roster_import_row表",
    "roster_import_operation.employee_id": "关联员工ID",
    "roster_import_operation.operation_type": "操作类型（如CREATE_EMPLOYEE/UPDATE_EMPLOYMENT）",
    "roster_import_operation.target_table": "操作目标表名",
    "roster_import_operation.target_id": "操作目标记录ID",
    "roster_import_operation.before_snapshot_json": "操作前快照（JSON），用于回滚",
    "roster_import_operation.after_snapshot_json": "操作后快照（JSON）",
    "roster_import_operation.reversible": "是否可回滚",
    "roster_import_operation.irreversible_reason": "不可回滚的原因说明",

    # ========== roster_column_alias ==========
    "roster_column_alias.source_header_normalized": "标准化后的表头名称（去空格转大写）",
    "roster_column_alias.target_field_key": "映射的目标字段标识",
    "roster_column_alias.enabled": "是否启用此映射",

    # ========== roster_value_alias ==========
    "roster_value_alias.field_key": "字段标识",
    "roster_value_alias.source_value_normalized": "标准化后的原始值",
    "roster_value_alias.target_value": "映射后的目标值",

    # ========== hr_confirmation_item ==========
    "hr_confirmation_item.employee_id": "员工ID，关联employee表",
    "hr_confirmation_item.employment_id": "任职记录ID，关联employment_record表",
    "hr_confirmation_item.source_type": "来源类型（如ROSTER_IMPORT）",
    "hr_confirmation_item.source_id": "来源系统中的原始ID",
    "hr_confirmation_item.issue_code": "问题/变更类型编码",
    "hr_confirmation_item.title": "确认事项标题",
    "hr_confirmation_item.description": "确认事项详细描述",
    "hr_confirmation_item.before_data_json": "变更前数据（JSON）",
    "hr_confirmation_item.after_data_json": "变更后数据（JSON）",
    "hr_confirmation_item.item_status": "处理状态：PENDING-待处理 APPROVED-已通过 REJECTED-已驳回",
    "hr_confirmation_item.handled_at": "处理时间",
    "hr_confirmation_item.import_batch_id": "导入批次ID",
    "hr_confirmation_item.import_row_id": "导入行ID",
}


def add_comments_to_file(filepath):
    """读取模型文件，为 mapped_column 添加 comment= 参数"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 获取表名
    table_match = re.search(r'__tablename__\s*=\s*["\'](\w+)["\']', content)
    if not table_match:
        # 检测是否是 base.py (CommonMixin)
        changes = 0
        if 'CommonMixin' in content and 'class CommonMixin' in content:
            result = _add_common_mixin_comments(content, filepath)
            if result:
                content = result
                changes += 1
        if 'class Base' in content and 'DeclarativeBase' in content:
            result = _add_base_comments(content, filepath)
            if result:
                content = result
                changes += 1
        if changes == 0:
            print(f"  SKIP: no tablename found in {filepath}")
        return None

    table_name = table_match.group(1)
    print(f"  Processing table: {table_name}")

    changes = 0

    # 查找所有 mapped_column( 并解析完整的括号范围
    # 逐字符扫描，找到所有 mapped_column 调用
    pos = 0
    result = []
    while pos < len(content):
        # 找下一个 mapped_column(
        mc_start = content.find('mapped_column(', pos)
        if mc_start == -1:
            result.append(content[pos:])
            break

        result.append(content[pos:mc_start])

        # 找到 mapped_column 后查找完整的括号对
        paren_start = content.index('(', mc_start)
        depth = 0
        i = paren_start
        while i < len(content):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            # 括号不完整，跳过
            result.append(content[mc_start:i+1])
            pos = i + 1
            continue

        # 完整的 mapped_column(...) 调用
        mc_call = content[mc_start:i+1]
        if 'comment=' in mc_call:
            # 已有注释，保持原样
            result.append(mc_call)
            pos = i + 1
            continue

        # 尝试获取列名：在 mapped_column 所在行的上一行找 <name>: Mapped
        # 先找到 mapped_column( 所在行
        line_start = content.rfind('\n', 0, mc_start)
        line_start = line_start + 1 if line_start != -1 else 0
        current_line = content[line_start:paren_start]

        name_match = re.search(r'^\s*(\w+)\s*:\s*Mapped', current_line)
        col_name = None
        if name_match:
            col_name = name_match.group(1)
        else:
            # 检查上一行
            prev_line_end = line_start
            if prev_line_end > 0:
                prev_line_start = content.rfind('\n', 0, prev_line_end - 1)
                prev_line_start = prev_line_start + 1 if prev_line_start != -1 else 0
                prev_line = content[prev_line_start:prev_line_end]
                name_match2 = re.search(r'^\s*(\w+)\s*:\s*Mapped', prev_line)
                if name_match2:
                    col_name = name_match2.group(1)

        if col_name:
            comment_key = f"{table_name}.{col_name}"
            comment_text = COLUMN_COMMENTS.get(comment_key)
            if comment_text:
                # 在最后一个 ) 前插入 , comment="..."
                # 需要处理多行时换行在 ) 前的问题
                close_paren = mc_call.rfind(')')
                # 检查 ) 前是否有换行和前导空格
                before_paren = mc_call[:close_paren]
                # 去掉紧邻 ) 前的空白/换行
                stripped = before_paren.rstrip()
                trailing_ws = before_paren[len(stripped):]
                # 如果末尾已经有个逗号，不需要再加逗号
                if stripped.endswith(','):
                    mc_call = stripped + f' comment="{comment_text}"' + trailing_ws + mc_call[close_paren:]
                else:
                    mc_call = stripped + f', comment="{comment_text}"' + trailing_ws + mc_call[close_paren:]
                changes += 1

        result.append(mc_call)
        pos = i + 1

    if changes > 0:
        new_content = ''.join(result)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Added {changes} comments")
        return new_content
    else:
        print(f"  - No changes needed")
        return None


def _add_common_mixin_comments(content, fp):
    """为 CommonMixin 添加注释"""
    changes = {
        'created_at': '创建时间',
        'created_by': '创建人',
        'updated_at': '最后更新时间',
        'updated_by': '最后更新人',
        'version': '乐观锁版本号，初始值1',
        'is_deleted': '逻辑删除标记，0=未删除 1=已删除',
        'deleted_at': '删除时间',
        'deleted_by': '删除人',
    }
    return _add_field_comments(content, changes, "CommonMixin", fp)


def _add_base_comments(content, fp):
    """为 Base 类添加注释"""
    changes = {
        'id': '主键ID，自增',
    }
    return _add_field_comments(content, changes, "Base", fp)


def _add_field_comments(content, field_comments, class_name, fp=None):
    """为特定类的字段添加 comment=，使用 content-scanning 方法"""
    changes = 0
    pos = 0
    result = []

    while pos < len(content):
        mc_start = content.find('mapped_column(', pos)
        if mc_start == -1:
            result.append(content[pos:])
            break

        result.append(content[pos:mc_start])

        # 找到映射行，获取列名
        line_start = content.rfind('\n', 0, mc_start)
        line_start = line_start + 1 if line_start != -1 else 0
        # 扫描到 mapped_column 所在行末尾或左括号
        paren_start = content.index('(', mc_start)
        current_line = content[line_start:paren_start]

        col_name = None
        for field_name in field_comments:
            if re.search(rf'^\s*{field_name}\s*:\s*Mapped', current_line):
                col_name = field_name
                break

        # 解析完整括号
        depth = 0
        i = paren_start
        while i < len(content):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            result.append(content[mc_start:i+1])
            pos = i + 1
            continue

        mc_call = content[mc_start:i+1]
        if col_name and 'comment=' not in mc_call:
            comment_text = field_comments[col_name]
            close_paren = mc_call.rfind(')')
            before_paren = mc_call[:close_paren]
            stripped = before_paren.rstrip()
            trailing_ws = before_paren[len(stripped):]
            if stripped.endswith(','):
                mc_call = stripped + f' comment="{comment_text}"' + trailing_ws + mc_call[close_paren:]
            else:
                mc_call = stripped + f', comment="{comment_text}"' + trailing_ws + mc_call[close_paren:]
            changes += 1

        result.append(mc_call)
        pos = i + 1

    if changes > 0:
        new_content = ''.join(result)
        target = fp or filepath
        with open(target, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Added {changes} comments to {class_name}")
        return new_content
    return None


if __name__ == '__main__':
    models_dir = Path(__file__).resolve().parent.parent / 'backend' / 'app' / 'models'
    print(f"Scanning models in: {models_dir}")

    for model_file in sorted(models_dir.glob('*.py')):
        if model_file.name == '__init__.py' or model_file.name == 'base.py':
            continue
        print(f"\nProcessing: {model_file.name}")
        add_comments_to_file(str(model_file))

    # 也处理 base.py
    print(f"\nProcessing: base.py")
    base_file = models_dir / 'base.py'
    add_comments_to_file(str(base_file))

    print("\nDone!")
