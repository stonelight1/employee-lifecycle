-- ================================================================
-- employee-lifecycle 数据库 MySQL DDL
-- 生成时间：2026-07-20 11:51:23
-- 来源：SQLAlchemy 模型元数据自动生成
-- 注意：每次修改模型后运行 scripts/generate_mysql_ddl.py 更新本文件
-- ================================================================

CREATE DATABASE IF NOT EXISTS employee_lifecycle
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE employee_lifecycle;

-- ---------------------------------------------------
-- 表：employee
-- ---------------------------------------------------
CREATE TABLE `employee` (
  `employee_no` VARCHAR(50) NULL COMMENT '员工工号',
  `name` VARCHAR(100) NOT NULL COMMENT '姓名',
  `normalized_name` VARCHAR(100) NOT NULL COMMENT '标准化姓名（去空格转大写，用于匹配与去重）',
  `mobile` VARCHAR(30) NULL COMMENT '手机号',
  `email` VARCHAR(200) NULL COMMENT '电子邮箱',
  `source_employee_key` VARCHAR(200) NULL COMMENT '外部来源系统中的员工唯一标识',
  `employee_status` VARCHAR(30) NOT NULL COMMENT '员工状态：ACTIVE-在职 INACTIVE-离职 ENTRY_ERROR-入职异常',
  `source` VARCHAR(100) NULL COMMENT '数据来源描述',
  `profile_completeness_status` VARCHAR(20) NULL COMMENT '档案完整度：COMPLETE-完整 INCOMPLETE-不完整',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_employee_employee_no` (`employee_no`),
  KEY `ix_employee_normalized_name` (`normalized_name`),
  UNIQUE KEY `uq_normalized_name_active` (`normalized_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工主表';

-- ---------------------------------------------------
-- 表：employee_profile
-- ---------------------------------------------------
CREATE TABLE `employee_profile` (
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表（唯一）',
  `identity_card` VARCHAR(50) NULL COMMENT '身份证号码',
  `gender` VARCHAR(10) NULL COMMENT '性别：MALE-男 FEMALE-女',
  `birth_date` DATE NULL COMMENT '出生日期',
  `household_registration` VARCHAR(500) NULL COMMENT '户籍地址',
  `residence_address` VARCHAR(500) NULL COMMENT '现居住地址',
  `household_type` VARCHAR(100) NULL COMMENT '户籍类型：URBAN-城镇 RURAL-农村',
  `graduation_school` VARCHAR(200) NULL COMMENT '毕业院校',
  `major` VARCHAR(200) NULL COMMENT '所学专业',
  `education_level` VARCHAR(50) NULL COMMENT '最高学历：ASSOCIATE-大专 BACHELOR-本科 MASTER-硕士 DOCTOR-博士',
  `social_insurance_policy` VARCHAR(50) NULL COMMENT '社保缴纳政策描述',
  `housing_fund_policy` VARCHAR(50) NULL COMMENT '公积金缴纳政策描述',
  `social_insurance_status` VARCHAR(200) NULL COMMENT '社保缴纳状态描述',
  `housing_fund_status` VARCHAR(200) NULL COMMENT '公积金缴纳状态描述',
  `social_insurance_start_date` DATE NULL COMMENT '社保开始缴纳日期',
  `housing_fund_start_date` DATE NULL COMMENT '公积金开始缴纳日期',
  `benefit_raw_text` TEXT NULL COMMENT '福利信息原始文本（来自花名册导入）',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_employee_profile_employee_id` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工档案/个人信息表';

-- ---------------------------------------------------
-- 表：employment_record
-- ---------------------------------------------------
CREATE TABLE `employment_record` (
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_seq` INT NOT NULL COMMENT '任职序号，同一员工从1开始递增',
  `employment_status` VARCHAR(30) NOT NULL COMMENT '任职状态：PENDING-待入职 ACTIVE-在职 SEPARATING-离职中 SEPARATED-已离职 CANCELLED-已取消',
  `hire_date` DATE NOT NULL COMMENT '入职日期（兼容旧数据，建议使用expected/actual_hire_date）',
  `expected_hire_date` DATE NULL COMMENT '预计入职日期',
  `actual_hire_date` DATE NULL COMMENT '实际入职日期',
  `probation_months` INT NOT NULL COMMENT '试用期月数，默认3个月',
  `probation_start_date` DATE NULL COMMENT '试用期开始日期',
  `probation_end_date` DATE NULL COMMENT '试用期结束日期',
  `probation_status` VARCHAR(30) NOT NULL COMMENT '试用期状态：NOT_STARTED-未开始 PROBATION-试用中 REGULARIZED-已转正 EXTENDED-已延长',
  `expected_regularization_date` DATE NULL COMMENT '预计转正日期',
  `actual_regularization_date` DATE NULL COMMENT '实际转正日期',
  `regularization_date` DATE NULL COMMENT '转正日期（兼容旧数据）',
  `employment_type` VARCHAR(30) NULL COMMENT '用工类型：FORMAL-正式 PROBATION-试用 INTERN-实习 CASUAL-兼职',
  `work_city` VARCHAR(100) NULL COMMENT '工作城市',
  `work_mode` VARCHAR(20) NULL COMMENT '工作模式：OFFICE-办公室 REMOTE-远程 HYBRID-混合 UNKNOWN-未知',
  `team_name` VARCHAR(200) NULL COMMENT '团队/组名称',
  `department` VARCHAR(200) NULL COMMENT '所属部门',
  `position` VARCHAR(200) NULL COMMENT '职位名称',
  `manager_name` VARCHAR(100) NULL COMMENT '直属上级姓名',
  `separation_date` DATE NULL COMMENT '离职日期',
  `status_before_separating` VARCHAR(30) NULL COMMENT '离职前的任职状态快照',
  `hire_cancelled_at` DATETIME NULL COMMENT '入职取消时间',
  `hire_cancel_reasons_json` TEXT NULL COMMENT '入职取消原因列表（JSON数组）',
  `hire_cancel_note` TEXT NULL COMMENT '入职取消备注说明',
  `date_rule_source` VARCHAR(50) NULL COMMENT '日期规则来源：IMPORT-导入 MANUAL-手动录入',
  `probation_end_date_source` VARCHAR(50) NULL COMMENT '试用期结束日期来源：COMPUTED-自动计算 IMPORT-导入 SPECIFIED-指定',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_employee_seq` (`employee_id`, `employment_seq`),
  KEY `ix_employment_record_employee_id` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='任职记录表';

-- ---------------------------------------------------
-- 表：employment_change
-- ---------------------------------------------------
CREATE TABLE `employment_change` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `change_type` VARCHAR(30) NOT NULL COMMENT '变更类型：DEPARTMENT-部门变更 POSITION-职位变更 MANAGER-上级变更',
  `effective_date` DATE NOT NULL COMMENT '变更生效日期',
  `before_data` TEXT NULL COMMENT '变更前数据快照（JSON）',
  `after_data` TEXT NULL COMMENT '变更后数据快照（JSON）',
  `reason` VARCHAR(500) NULL COMMENT '变更原因',
  `confirmed_by` VARCHAR(100) NULL COMMENT '确认人用户ID',
  `confirmed_at` DATETIME NULL COMMENT '确认时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_employment_change_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='任职异动记录表';

-- ---------------------------------------------------
-- 表：employment_contract
-- ---------------------------------------------------
CREATE TABLE `employment_contract` (
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_id` INT NULL COMMENT '任职记录ID，关联employment_record表',
  `contract_status` VARCHAR(50) NULL COMMENT '合同状态：ACTIVE-生效 EXPIRED-到期 TERMINATED-终止',
  `signing_company` VARCHAR(200) NULL COMMENT '合同签约公司（甲方）',
  `contract_type` VARCHAR(20) NULL COMMENT '合同类型：FIXED-固定期限 PERMANENT-无固定期限 PROJECT-项目合同 UNKNOWN-未知',
  `start_date` DATE NULL COMMENT '合同开始日期',
  `end_date` DATE NULL COMMENT '合同结束日期',
  `signing_sequence` INT NULL COMMENT '合同签署序号（第几次签约）',
  `source_type` VARCHAR(20) NOT NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `confirmed_at` DATETIME NULL COMMENT '合同确认时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_employment_contract_employment_id` (`employment_id`),
  KEY `ix_employment_contract_employee_id` (`employee_id`),
  KEY `ix_contract_employee_employment` (`employee_id`, `employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='劳动合同信息表';

-- ---------------------------------------------------
-- 表：compensation_record
-- ---------------------------------------------------
CREATE TABLE `compensation_record` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_id` INT NULL COMMENT '任职记录ID，关联employment_record表',
  `raw_salary_text` TEXT NULL COMMENT '原始薪资文本（来自花名册）',
  `salary_type` VARCHAR(10) NULL COMMENT '薪资类型：MONTHLY-月薪 DAILY-日薪 HOURLY-时薪 UNKNOWN-未知',
  `base_salary` DECIMAL(12,2) NULL COMMENT '基本工资金额',
  `probation_salary` DECIMAL(12,2) NULL COMMENT '试用期工资金额',
  `regular_salary` DECIMAL(12,2) NULL COMMENT '转正后工资金额',
  `daily_rate` DECIMAL(12,2) NULL COMMENT '日薪金额',
  `performance_amount` DECIMAL(12,2) NULL COMMENT '绩效工资金额',
  `performance_ratio` DECIMAL(5,2) NULL COMMENT '绩效比例，如0.1表示10%',
  `commission_text` TEXT NULL COMMENT '提成/佣金说明',
  `other_text` TEXT NULL COMMENT '其他薪资相关说明',
  `effective_date` DATE NULL COMMENT '薪酬生效日期',
  `source_type` VARCHAR(20) NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `import_batch_id` INT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_compensation_record_employment_id` (`employment_id`),
  KEY `ix_compensation_record_employee_id` (`employee_id`),
  KEY `ix_compensation_employee_effective` (`employee_id`, `employment_id`, `effective_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='薪酬记录表';

-- ---------------------------------------------------
-- 表：employee_financial_account
-- ---------------------------------------------------
CREATE TABLE `employee_financial_account` (
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `account_type` VARCHAR(10) NOT NULL COMMENT '账户类型：BANK-银行卡 ALIPAY-支付宝 WECHAT-微信支付',
  `account_no` VARCHAR(200) NOT NULL COMMENT '银行账号/支付账户号',
  `bank_name` VARCHAR(200) NULL COMMENT '开户银行名称',
  `is_primary` TINYINT(1) NOT NULL COMMENT '是否为主账户',
  `account_status` VARCHAR(10) NOT NULL COMMENT '账户状态：ACTIVE-有效 INACTIVE-停用',
  `source_type` VARCHAR(20) NOT NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `confirmed_at` DATETIME NULL COMMENT '账户确认时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_employee_financial_account_employee_id` (`employee_id`),
  KEY `ix_financial_account_employee` (`employee_id`, `account_type`, `account_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工财务账户（银行卡/支付宝等）';

-- ---------------------------------------------------
-- 表：employee_assessment
-- ---------------------------------------------------
CREATE TABLE `employee_assessment` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `assessment_type` VARCHAR(10) NOT NULL COMMENT '考核类型：INTERVIEW-面试 PROBATION-试用期 ANNUAL-年度',
  `result_text` TEXT NULL COMMENT '考核结果文本内容',
  `attachment_path` VARCHAR(500) NULL COMMENT '考核附件文件路径',
  `assessment_date` DATE NULL COMMENT '考核日期',
  `source_type` VARCHAR(20) NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `import_batch_id` INT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_employee_assessment_employee_id` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工考核/评估记录表';

-- ---------------------------------------------------
-- 表：employee_note
-- ---------------------------------------------------
CREATE TABLE `employee_note` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_id` INT NULL COMMENT '任职记录ID，关联employment_record表',
  `content` TEXT NOT NULL COMMENT '备注内容',
  `source_type` VARCHAR(20) NOT NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `source_id` VARCHAR(100) NULL COMMENT '来源系统中的原始ID',
  `import_batch_id` INT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `source_row_no` INT NULL COMMENT '来源文件中的行号',
  `content_hash` VARCHAR(64) NULL COMMENT '备注内容SHA256哈希，用于去重',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_employee_note_employee_id` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工备注表';

-- ---------------------------------------------------
-- 表：employee_attribute_history
-- ---------------------------------------------------
CREATE TABLE `employee_attribute_history` (
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_id` INT NULL COMMENT '任职记录ID，关联employment_record表',
  `category` VARCHAR(50) NULL COMMENT '属性分类（如EMPLOYMENT/CONTACT/PROFILE）',
  `field_name` VARCHAR(100) NOT NULL COMMENT '发生变更的字段名',
  `before_value_json` TEXT NULL COMMENT '变更前值（JSON格式）',
  `after_value_json` TEXT NULL COMMENT '变更后值（JSON格式）',
  `effective_date` DATE NULL COMMENT '变更生效日期',
  `source_type` VARCHAR(20) NOT NULL COMMENT '数据来源类型：IMPORT-导入 MANUAL-手工',
  `source_id` VARCHAR(100) NULL COMMENT '来源系统中的原始ID',
  `import_batch_id` INT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `operator_name` VARCHAR(100) NULL COMMENT '操作人姓名',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_employee_attribute_history_employee_id` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='员工属性变更历史表';

-- ---------------------------------------------------
-- 表：followup_node_definition
-- ---------------------------------------------------
CREATE TABLE `followup_node_definition` (
  `node_code` VARCHAR(50) NOT NULL COMMENT '节点编码，唯一标识',
  `node_name` VARCHAR(200) NOT NULL COMMENT '节点名称',
  `trigger_type` VARCHAR(50) NOT NULL COMMENT '触发类型：DAYS_AFTER_HIRE-入职后天数 DAYS_AFTER_REGULAR-转正后天数',
  `offset_days` INT NULL COMMENT '相对于触发事件的天数偏移',
  `enabled` TINYINT(1) NOT NULL COMMENT '是否启用，默认TRUE',
  `default_assignee_rule` VARCHAR(200) NULL COMMENT '默认负责人分配规则',
  `confirmation_mode` VARCHAR(10) NOT NULL COMMENT '确认模式：ALL-全部确认 ANY-任一确认即可',
  `node_version` INT NOT NULL COMMENT '节点定义版本号',
  `effective_from` DATE NULL COMMENT '生效开始日期',
  `effective_to` DATE NULL COMMENT '生效结束日期',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='跟进节点定义表';

-- ---------------------------------------------------
-- 表：followup_task
-- ---------------------------------------------------
CREATE TABLE `followup_task` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `node_definition_id` INT NULL COMMENT '关联的节点定义ID',
  `node_version` INT NULL COMMENT '生成任务时节点定义的版本快照',
  `node_code_snapshot` VARCHAR(50) NULL COMMENT '节点编码快照',
  `task_name` VARCHAR(200) NOT NULL COMMENT '任务名称',
  `task_source` VARCHAR(10) NOT NULL COMMENT '任务来源：AUTO-自动创建 MANUAL-手动创建',
  `trigger_type_snapshot` VARCHAR(50) NULL COMMENT '触发类型快照',
  `offset_days_snapshot` INT NULL COMMENT '偏移天数快照',
  `planned_date` DATE NOT NULL COMMENT '计划执行日期',
  `original_planned_date` DATE NULL COMMENT '原始计划日期（手动调整前）',
  `date_adjusted_manually` TINYINT(1) NOT NULL COMMENT '计划日期是否被手动调整过',
  `followup_status` VARCHAR(30) NOT NULL COMMENT '任务状态：PENDING-待处理 IN_PROGRESS-进行中 COMPLETED-已完成 CANCELLED-已取消',
  `confirmation_mode` VARCHAR(10) NOT NULL COMMENT '确认模式快照：ALL-全部确认 ANY-任一确认',
  `completed_at` DATETIME NULL COMMENT '任务完成时间',
  `completed_by` VARCHAR(100) NULL COMMENT '任务完成人用户ID',
  `cancel_reason` TEXT NULL COMMENT '取消原因',
  `idempotency_key` VARCHAR(200) NULL COMMENT '幂等键，防止重复创建',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_followup_task_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='跟进任务表';

-- ---------------------------------------------------
-- 表：followup_task_participant
-- ---------------------------------------------------
CREATE TABLE `followup_task_participant` (
  `task_id` INT NOT NULL COMMENT '任务ID，关联followup_task表',
  `user_id` VARCHAR(100) NOT NULL COMMENT '参与者用户ID',
  `participant_role` VARCHAR(30) NOT NULL COMMENT '参与角色：RESPONSIBLE-负责人 PARTICIPANT-参与人 OBSERVER-观察者',
  `active` TINYINT(1) NOT NULL COMMENT '是否活跃参与者，默认TRUE',
  `assigned_at` DATETIME NOT NULL COMMENT '分配时间',
  `removed_at` DATETIME NULL COMMENT '移除时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_task_participant` (`task_id`, `user_id`),
  KEY `ix_followup_task_participant_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='跟进任务参与人表';

-- ---------------------------------------------------
-- 表：followup_task_confirmation
-- ---------------------------------------------------
CREATE TABLE `followup_task_confirmation` (
  `task_id` INT NOT NULL COMMENT '任务ID，关联followup_task表',
  `user_id` VARCHAR(100) NOT NULL COMMENT '参与者用户ID',
  `confirmation_status` VARCHAR(30) NOT NULL COMMENT '确认状态：PENDING-待确认 CONFIRMED-已确认 REJECTED-已拒绝',
  `comment` TEXT NULL COMMENT '确认意见',
  `confirmed_at` DATETIME NULL COMMENT '确认时间',
  `request_id` VARCHAR(200) NULL COMMENT '确认请求标识',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_task_confirmation` (`task_id`, `user_id`, `request_id`),
  KEY `ix_followup_task_confirmation_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='跟进任务确认记录表';

-- ---------------------------------------------------
-- 表：communication_record
-- ---------------------------------------------------
CREATE TABLE `communication_record` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `followup_task_id` INT NULL COMMENT '关联的跟进任务ID',
  `communication_type` VARCHAR(50) NULL COMMENT '沟通类型：PHONE-电话 FACE_TO_FACE-面谈 VIDEO-视频',
  `communication_at` DATETIME NULL COMMENT '沟通发生时间',
  `hr_user_id` VARCHAR(100) NULL COMMENT '执行沟通的HR用户ID',
  `communication_status` VARCHAR(30) NOT NULL COMMENT '沟通记录状态：DRAFT-草稿 FINALIZED-已完成',
  `current_text_version_id` INT NULL COMMENT '当前沟通文本版本ID',
  `current_text_version_no` INT NULL COMMENT '当前沟通文本版本号',
  `current_text_hash` VARCHAR(64) NULL COMMENT '当前沟通文本内容哈希',
  `manual_summary` TEXT NULL COMMENT 'HR手动撰写的沟通摘要',
  `hr_conclusion` TEXT NULL COMMENT 'HR沟通结论',
  `source` VARCHAR(50) NULL COMMENT '沟通来源：SYSTEM-系统 AUTO-自动 CREATED-手动创建',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_communication_record_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='沟通记录表';

-- ---------------------------------------------------
-- 表：communication_text_version
-- ---------------------------------------------------
CREATE TABLE `communication_text_version` (
  `communication_id` INT NOT NULL COMMENT '沟通记录ID，关联communication_record表',
  `version_no` INT NOT NULL COMMENT '版本号，从1开始递增',
  `text_content` TEXT NOT NULL COMMENT '沟通文本内容',
  `text_hash` VARCHAR(64) NULL COMMENT '文本内容SHA256哈希',
  `text_length` INT NOT NULL COMMENT '文本字符长度',
  `change_reason` VARCHAR(500) NULL COMMENT '变更原因说明',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_comm_text_version` (`communication_id`, `version_no`),
  KEY `ix_communication_text_version_communication_id` (`communication_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='沟通文本版本历史表';

-- ---------------------------------------------------
-- 表：ai_summary_version
-- ---------------------------------------------------
CREATE TABLE `ai_summary_version` (
  `communication_id` INT NOT NULL COMMENT '沟通记录ID，关联communication_record表',
  `version_no` INT NOT NULL COMMENT 'AI摘要版本号',
  `source_text_version_id` INT NULL COMMENT '源文本版本ID',
  `source_text_version_no` INT NULL COMMENT '源文本版本号',
  `source_text_hash` VARCHAR(64) NULL COMMENT '源文本哈希值',
  `provider` VARCHAR(100) NULL COMMENT 'AI服务提供商（如openai/anthropic）',
  `model_name` VARCHAR(100) NULL COMMENT 'AI模型名称（如gpt-4/claude-opus-4）',
  `prompt_version` VARCHAR(50) NULL COMMENT '使用的提示词版本号',
  `prompt_snapshot` TEXT NULL COMMENT '提示词内容快照',
  `output_schema_version` VARCHAR(50) NULL COMMENT '输出JSON Schema版本号',
  `summary_status` VARCHAR(30) NOT NULL COMMENT '摘要生成状态：PROCESSING-处理中 SUCCESS-成功 FAILED-失败',
  `structured_summary` TEXT NULL COMMENT '结构化的AI摘要内容（JSON）',
  `raw_response_ref` VARCHAR(500) NULL COMMENT 'AI原始响应引用路径或标识',
  `is_ai_suggestion` TINYINT(1) NOT NULL COMMENT '是否为AI建议（未被人工确认）',
  `is_current` TINYINT(1) NOT NULL COMMENT '是否为当前生效版本',
  `is_stale` TINYINT(1) NOT NULL COMMENT '是否因文本更新而过期',
  `started_at` DATETIME NULL COMMENT 'AI调用开始时间',
  `finished_at` DATETIME NULL COMMENT 'AI调用完成时间',
  `failure_type` VARCHAR(50) NULL COMMENT '失败类型（如TIMEOUT/INVALID_RESPONSE）',
  `failure_reason` TEXT NULL COMMENT '失败原因描述',
  `retry_count` INT NOT NULL COMMENT '已重试次数',
  `idempotency_key` VARCHAR(200) NULL COMMENT '幂等键，保证同一请求不会重复处理',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_summary_version` (`communication_id`, `version_no`),
  KEY `ix_ai_summary_version_communication_id` (`communication_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='AI摘要版本表';

-- ---------------------------------------------------
-- 表：risk_assessment
-- ---------------------------------------------------
CREATE TABLE `risk_assessment` (
  `communication_id` INT NOT NULL COMMENT '沟通记录ID，关联communication_record表',
  `source_text_version_id` INT NULL COMMENT '风险评估依据的文本版本ID',
  `ai_summary_version_id` INT NULL COMMENT '使用的AI摘要版本ID，关联ai_summary_version表',
  `assessment_source` VARCHAR(10) NOT NULL COMMENT '评估来源：AI-自动评估 HR-人工评估',
  `ai_risk_level` VARCHAR(20) NULL COMMENT 'AI判断的风险等级：HIGH-高 MEDIUM-中 LOW-低 UNSPECIFIED-未指定',
  `ai_risk_reasons` TEXT NULL COMMENT 'AI判断风险的原因说明',
  `ai_evidence` TEXT NULL COMMENT 'AI引用的风险证据文本',
  `ai_followup_suggestions` TEXT NULL COMMENT 'AI建议的跟进措施',
  `risk_review_status` VARCHAR(30) NOT NULL COMMENT '风险审核状态：PENDING_REVIEW-待审核 REVIEWED-已审核',
  `hr_risk_level` VARCHAR(20) NULL COMMENT 'HR认定风险等级',
  `hr_comment` TEXT NULL COMMENT 'HR评审意见',
  `reviewed_by` VARCHAR(100) NULL COMMENT '审核人用户ID',
  `reviewed_at` DATETIME NULL COMMENT '审核时间',
  `is_current` TINYINT(1) NOT NULL COMMENT '是否为当前有效的风险评估',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_risk_assessment_communication_id` (`communication_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='风险评估记录表';

-- ---------------------------------------------------
-- 表：probation_review
-- ---------------------------------------------------
CREATE TABLE `probation_review` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `followup_task_id` INT NULL COMMENT '关联的跟进任务ID',
  `communication_id` INT NULL COMMENT '关联的沟通记录ID',
  `review_seq` INT NOT NULL COMMENT '试用期评审序号',
  `review_stage` VARCHAR(20) NOT NULL COMMENT '评审阶段：FOLLOWUP-跟进评审 FINAL-终期评审',
  `review_status` VARCHAR(30) NULL COMMENT '评审状态：PENDING-待评审 COMPLETED-已完成 SKIPPED-已跳过',
  `hr_evaluation` TEXT NULL COMMENT 'HR评价内容',
  `employee_feedback` TEXT NULL COMMENT '员工反馈内容',
  `recommendation` VARCHAR(500) NULL COMMENT '评审建议（如建议转正/延长/解除）',
  `reviewed_by` VARCHAR(100) NULL COMMENT '评审人用户ID',
  `reviewed_at` DATETIME NULL COMMENT '评审完成时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_probation_review_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='试用期评审记录表';

-- ---------------------------------------------------
-- 表：regularization_record
-- ---------------------------------------------------
CREATE TABLE `regularization_record` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `probation_review_id` INT NULL COMMENT '关联的试用期评审ID',
  `decision` VARCHAR(30) NOT NULL COMMENT '转正决定：APPROVED-通过 EXTENDED-延长 NOT_APPROVED-不通过',
  `effective_date` DATE NULL COMMENT '转正生效日期',
  `new_probation_end_date` DATE NULL COMMENT '延长后的新试用期结束日期',
  `decision_reason` TEXT NULL COMMENT '转正决定的原因说明',
  `ai_summary_version_id` INT NULL COMMENT '使用的AI摘要版本ID',
  `confirmed_by` VARCHAR(100) NULL COMMENT '确认人用户ID',
  `confirmed_at` DATETIME NULL COMMENT '确认时间',
  `is_effective` TINYINT(1) NOT NULL COMMENT '是否已生效，默认TRUE',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_regularization_record_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='转正审批记录表';

-- ---------------------------------------------------
-- 表：separation_record
-- ---------------------------------------------------
CREATE TABLE `separation_record` (
  `employment_id` INT NOT NULL COMMENT '任职记录ID，关联employment_record表',
  `planned_separation_date` DATE NULL COMMENT '计划离职日期',
  `actual_separation_date` DATE NULL COMMENT '实际离职日期',
  `separation_type` VARCHAR(50) NULL COMMENT '离职类型：RESIGNATION-主动辞职 TERMINATION-公司解除 RETIREMENT-退休',
  `reason` TEXT NULL COMMENT '离职原因说明',
  `hr_comment` TEXT NULL COMMENT 'HR备注意见',
  `confirmed_by` VARCHAR(100) NULL COMMENT '确认人用户ID',
  `confirmed_at` DATETIME NULL COMMENT '确认时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_separation_record_employment_id` (`employment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='离职记录表';

-- ---------------------------------------------------
-- 表：separation_checklist_item
-- ---------------------------------------------------
CREATE TABLE `separation_checklist_item` (
  `separation_record_id` INT NOT NULL COMMENT '离职记录ID，关联separation_record表',
  `item_type` VARCHAR(30) NOT NULL COMMENT '清单项类型：ASSET_RETURN-资产归还 SYSTEM_LOGOFF-系统注销 DOCUMENT-文档',
  `title` VARCHAR(500) NOT NULL COMMENT '清单项标题',
  `completed` TINYINT(1) NOT NULL COMMENT '是否已完成，默认FALSE',
  `completed_at` DATETIME NULL COMMENT '完成时间',
  `remark` TEXT NULL COMMENT '备注说明',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_separation_checklist_item_separation_record_id` (`separation_record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='离职清单项表';

-- ---------------------------------------------------
-- 表：system_todo
-- ---------------------------------------------------
CREATE TABLE `system_todo` (
  `user_id` VARCHAR(100) NOT NULL COMMENT '待办所属用户ID',
  `business_type` VARCHAR(50) NOT NULL COMMENT '业务类型，如REGULARIZATION_REVIEW/SEPARATION_CHECK',
  `business_id` INT NOT NULL COMMENT '业务记录ID',
  `title` VARCHAR(500) NOT NULL COMMENT '待办事项标题',
  `due_at` DATE NULL COMMENT '截止日期',
  `todo_status` VARCHAR(30) NOT NULL COMMENT '待办状态：PENDING-待处理 COMPLETED-已完成 CANCELLED-已取消',
  `priority` VARCHAR(20) NULL COMMENT '优先级：HIGH-高 MEDIUM-中 LOW-低',
  `source` VARCHAR(50) NULL COMMENT '待办来源描述',
  `idempotency_key` VARCHAR(200) NULL COMMENT '幂等键，防止重复创建',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_system_todo_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='系统待办事项表';

-- ---------------------------------------------------
-- 表：operation_log
-- ---------------------------------------------------
CREATE TABLE `operation_log` (
  `operator_id` VARCHAR(100) NOT NULL COMMENT '操作人用户ID',
  `operated_at` DATETIME NOT NULL COMMENT '操作时间',
  `object_type` VARCHAR(50) NOT NULL COMMENT '操作对象类型（表名/实体名）',
  `object_id` VARCHAR(100) NOT NULL COMMENT '操作对象的主键ID',
  `operation_type` VARCHAR(50) NOT NULL COMMENT '操作类型：CREATE-创建 UPDATE-更新 DELETE-删除',
  `before_data` TEXT NULL COMMENT '操作前数据快照（JSON）',
  `after_data` TEXT NULL COMMENT '操作后数据快照（JSON）',
  `operation_source` VARCHAR(100) NULL COMMENT '操作来源描述',
  `business_id` INT NULL COMMENT '业务记录ID，用于关联查询',
  `request_id` VARCHAR(100) NULL COMMENT '请求追踪ID，用于关联同一请求的多个操作',
  `ip_address` VARCHAR(50) NULL COMMENT '操作人IP地址',
  `user_agent` VARCHAR(500) NULL COMMENT '操作人User-Agent',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_operation_log_operator_id` (`operator_id`),
  KEY `ix_operation_log_request_id` (`request_id`),
  KEY `ix_operation_log_operated_at` (`operated_at`),
  KEY `ix_oplog_object` (`object_type`, `object_id`),
  KEY `ix_operation_log_business_id` (`business_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='操作审计日志表';

-- ---------------------------------------------------
-- 表：organization_reference
-- ---------------------------------------------------
CREATE TABLE `organization_reference` (
  `reference_type` VARCHAR(15) NOT NULL COMMENT '参考数据类型：DEPARTMENT-部门 POSITION-职位',
  `name` VARCHAR(200) NOT NULL COMMENT '名称',
  `normalized_name` VARCHAR(200) NOT NULL COMMENT '标准化名称（去空格转大写，用于匹配）',
  `enabled` TINYINT(1) NOT NULL COMMENT '是否启用，默认TRUE',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='组织架构参考数据表（部门/职位字典）';

-- ---------------------------------------------------
-- 表：hr_confirmation_item
-- ---------------------------------------------------
CREATE TABLE `hr_confirmation_item` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `employee_id` INT NOT NULL COMMENT '员工ID，关联employee表',
  `employment_id` INT NULL COMMENT '任职记录ID，关联employment_record表',
  `source_type` VARCHAR(50) NOT NULL COMMENT '来源类型（如ROSTER_IMPORT）',
  `source_id` VARCHAR(100) NULL COMMENT '来源系统中的原始ID',
  `issue_code` VARCHAR(50) NOT NULL COMMENT '问题/变更类型编码',
  `title` VARCHAR(500) NOT NULL COMMENT '确认事项标题',
  `description` TEXT NULL COMMENT '确认事项详细描述',
  `before_data_json` TEXT NULL COMMENT '变更前数据（JSON）',
  `after_data_json` TEXT NULL COMMENT '变更后数据（JSON）',
  `import_batch_id` INT NULL COMMENT '导入批次ID',
  `import_row_id` INT NULL COMMENT '导入行ID',
  `item_status` VARCHAR(15) NOT NULL COMMENT '处理状态：PENDING-待处理 APPROVED-已通过 REJECTED-已驳回',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `handled_at` DATETIME NULL COMMENT '处理时间',
  PRIMARY KEY (`id`),
  KEY `ix_hr_confirmation_employee` (`employee_id`, `item_status`),
  KEY `ix_hr_confirmation_item_employee_id` (`employee_id`),
  KEY `ix_hr_confirmation_batch` (`import_batch_id`, `item_status`),
  KEY `ix_hr_confirmation_status` (`item_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='HR确认事项表（花名册导入需人工确认项）';

-- ---------------------------------------------------
-- 表：roster_import_batch
-- ---------------------------------------------------
CREATE TABLE `roster_import_batch` (
  `batch_no` VARCHAR(50) NOT NULL COMMENT '导入批次号，唯一',
  `mode` VARCHAR(15) NOT NULL COMMENT '导入模式：SYNC-同步导入 ASYNC-异步导入',
  `file_name` VARCHAR(500) NOT NULL COMMENT '上传的原始文件名',
  `stored_file_path` VARCHAR(1000) NOT NULL COMMENT '文件存储路径',
  `file_sha256` VARCHAR(64) NOT NULL COMMENT '文件SHA256哈希值，用于去重',
  `file_size` INT NOT NULL COMMENT '文件大小（字节）',
  `sheet_name` VARCHAR(200) NULL COMMENT '工作表名称（Excel多sheet时）',
  `header_row` TEXT NOT NULL COMMENT '表头行内容（JSON数组）',
  `batch_status` VARCHAR(30) NOT NULL COMMENT '批次状态：UPLOADED-已上传 PARSED-已解析 REVIEWING-审核中 IMPORTED-已导入 FAILED-失败 ROLLED_BACK-已回滚',
  `header_row_index` INT NULL COMMENT '表头所在行号（0-based）',
  `column_mappings_json` TEXT NULL COMMENT '列映射配置（JSON），存储表头到字段的映射关系',
  `total_rows` INT NOT NULL COMMENT '总行数',
  `new_count` INT NOT NULL COMMENT '新增员工数',
  `update_count` INT NOT NULL COMMENT '更新员工数',
  `unchanged_count` INT NOT NULL COMMENT '无变化行数',
  `confirmation_count` INT NOT NULL COMMENT '需人工确认数',
  `warning_count` INT NOT NULL COMMENT '警告数',
  `error_count` INT NOT NULL COMMENT '错误数',
  `skipped_count` INT NOT NULL COMMENT '跳过行数（如合作地区）',
  `imported_count` INT NOT NULL COMMENT '实际导入行数',
  `started_at` DATETIME NULL COMMENT '处理开始时间',
  `completed_at` DATETIME NULL COMMENT '处理完成时间',
  `failed_at` DATETIME NULL COMMENT '失败时间',
  `failure_message` TEXT NULL COMMENT '失败原因',
  `rolled_back_at` DATETIME NULL COMMENT '回滚时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  KEY `ix_roster_import_batch_file_sha256` (`file_sha256`),
  KEY `ix_roster_batch_sha256` (`file_sha256`),
  KEY `ix_roster_batch_status` (`batch_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册导入批次表';

-- ---------------------------------------------------
-- 表：roster_import_row
-- ---------------------------------------------------
CREATE TABLE `roster_import_row` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `batch_id` INT NOT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `row_no` INT NOT NULL COMMENT '行号（从1开始）',
  `employee_id` INT NULL COMMENT '匹配到的员工ID（新增时为NULL）',
  `normalized_name` VARCHAR(100) NOT NULL COMMENT '标准化后的员工姓名',
  `match_type` VARCHAR(50) NULL COMMENT '匹配方式：NEW-新建 MATCH-匹配到已有员工',
  `row_status` VARCHAR(30) NOT NULL COMMENT '行处理状态：NEW-待处理 MATCHED-已匹配 REVIEWING-审核中',
  `import_action` VARCHAR(15) NULL COMMENT '导入动作：CREATE-新增 UPDATE-更新 SKIP-跳过',
  `review_status` VARCHAR(25) NULL COMMENT '审核状态：PENDING-待审核 APPROVED-已通过 REJECTED-已驳回',
  `execution_status` VARCHAR(15) NULL COMMENT '执行状态：PENDING-待执行 SUCCESS-成功 FAILED-失败',
  `lifecycle_decision_json` TEXT NULL COMMENT '生命周期决策（JSON）',
  `raw_data_json` TEXT NULL COMMENT '原始行数据（JSON，按表头键值对）',
  `normalized_data_json` TEXT NULL COMMENT '标准化后的行数据（JSON）',
  `diff_json` TEXT NULL COMMENT '与现有数据的差异对比（JSON）',
  `planned_actions_json` TEXT NULL COMMENT '计划执行的操作列表（JSON）',
  `result_json` TEXT NULL COMMENT '执行结果（JSON）',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_roster_row_batch_row` (`batch_id`, `row_no`),
  KEY `ix_roster_row_execution` (`batch_id`, `execution_status`),
  KEY `ix_roster_row_review` (`batch_id`, `review_status`),
  KEY `ix_roster_row_batch_status` (`batch_id`, `row_status`),
  KEY `ix_roster_import_row_batch_id` (`batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册导入行数据表';

-- ---------------------------------------------------
-- 表：roster_import_issue
-- ---------------------------------------------------
CREATE TABLE `roster_import_issue` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `batch_id` INT NOT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `row_id` INT NULL COMMENT '关联行ID，关联roster_import_row表',
  `employee_id` INT NULL COMMENT '关联员工ID',
  `field_key` VARCHAR(100) NULL COMMENT '引起问题的字段标识',
  `issue_code` VARCHAR(50) NOT NULL COMMENT '问题编码，用于前端i18n和分类处理',
  `severity` VARCHAR(10) NOT NULL COMMENT '严重程度：ERROR-错误 WARNING-警告 INFO-提示',
  `title` VARCHAR(500) NOT NULL COMMENT '问题标题',
  `message` TEXT NULL COMMENT '问题详细描述',
  `old_value_json` TEXT NULL COMMENT '原始值（JSON）',
  `new_value_json` TEXT NULL COMMENT '新值（JSON）',
  `allowed_actions_json` TEXT NULL COMMENT '允许的解决操作列表（JSON）',
  `resolution_status` VARCHAR(15) NOT NULL COMMENT '解决状态：PENDING-待处理 RESOLVED-已解决 DISMISSED-已忽略',
  `resolution_action` VARCHAR(50) NULL COMMENT '解决时执行的操作',
  `resolution_value_json` TEXT NULL COMMENT '解决后的值（JSON）',
  `resolution_note` TEXT NULL COMMENT '解决备注',
  `resolved_at` DATETIME NULL COMMENT '解决时间',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_roster_import_issue_batch_id` (`batch_id`),
  KEY `ix_roster_issue_batch_status` (`batch_id`, `resolution_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册导入问题表';

-- ---------------------------------------------------
-- 表：roster_import_operation
-- ---------------------------------------------------
CREATE TABLE `roster_import_operation` (
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  `batch_id` INT NOT NULL COMMENT '导入批次ID，关联roster_import_batch表',
  `row_id` INT NULL COMMENT '关联行ID，关联roster_import_row表',
  `employee_id` INT NULL COMMENT '关联员工ID',
  `operation_type` VARCHAR(50) NOT NULL COMMENT '操作类型（如CREATE_EMPLOYEE/UPDATE_EMPLOYMENT）',
  `target_table` VARCHAR(50) NOT NULL COMMENT '操作目标表名',
  `target_id` INT NULL COMMENT '操作目标记录ID',
  `before_snapshot_json` TEXT NULL COMMENT '操作前快照（JSON），用于回滚',
  `after_snapshot_json` TEXT NULL COMMENT '操作后快照（JSON）',
  `reversible` TINYINT(1) NOT NULL COMMENT '是否可回滚',
  `irreversible_reason` TEXT NULL COMMENT '不可回滚的原因说明',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_roster_operation_employee` (`employee_id`),
  KEY `ix_roster_operation_batch` (`batch_id`),
  KEY `ix_roster_import_operation_batch_id` (`batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册导入操作记录表';

-- ---------------------------------------------------
-- 表：roster_column_alias
-- ---------------------------------------------------
CREATE TABLE `roster_column_alias` (
  `source_header_normalized` VARCHAR(200) NOT NULL COMMENT '标准化后的表头名称（去空格转大写）',
  `target_field_key` VARCHAR(100) NOT NULL COMMENT '映射的目标字段标识',
  `enabled` TINYINT(1) NOT NULL COMMENT '是否启用此映射',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册表头别名映射表';

-- ---------------------------------------------------
-- 表：roster_value_alias
-- ---------------------------------------------------
CREATE TABLE `roster_value_alias` (
  `field_key` VARCHAR(100) NOT NULL COMMENT '字段标识',
  `source_value_normalized` VARCHAR(200) NOT NULL COMMENT '标准化后的原始值',
  `target_value` VARCHAR(200) NOT NULL COMMENT '映射后的目标值',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `created_by` VARCHAR(100) NULL COMMENT '创建人',
  `updated_at` DATETIME NULL COMMENT '最后更新时间',
  `updated_by` VARCHAR(100) NULL COMMENT '最后更新人',
  `version` INT NOT NULL COMMENT '乐观锁版本号，初始值1',
  `is_deleted` TINYINT(1) NOT NULL COMMENT '逻辑删除标记，0=未删除 1=已删除',
  `deleted_at` DATETIME NULL COMMENT '删除时间',
  `deleted_by` VARCHAR(100) NULL COMMENT '删除人',
  `id` INT AUTO_INCREMENT NOT NULL COMMENT '主键ID，自增',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_roster_value_alias` (`field_key`, `source_value_normalized`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='花名册值别名映射表';

-- ================================================================
-- 外键约束
-- ================================================================
ALTER TABLE `employee_profile` ADD CONSTRAINT `fk_employee_profile_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employment_record` ADD CONSTRAINT `fk_employment_record_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employment_change` ADD CONSTRAINT `fk_employment_change_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employment_contract` ADD CONSTRAINT `fk_employment_contract_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employment_contract` ADD CONSTRAINT `fk_employment_contract_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `compensation_record` ADD CONSTRAINT `fk_compensation_record_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `compensation_record` ADD CONSTRAINT `fk_compensation_record_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_financial_account` ADD CONSTRAINT `fk_employee_financial_account_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_assessment` ADD CONSTRAINT `fk_employee_assessment_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_note` ADD CONSTRAINT `fk_employee_note_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_note` ADD CONSTRAINT `fk_employee_note_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_note` ADD CONSTRAINT `fk_employee_note_import_batch_id`
  FOREIGN KEY (`import_batch_id`) REFERENCES `roster_import_batch` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_attribute_history` ADD CONSTRAINT `fk_employee_attribute_history_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_attribute_history` ADD CONSTRAINT `fk_employee_attribute_history_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `employee_attribute_history` ADD CONSTRAINT `fk_employee_attribute_history_import_batch_id`
  FOREIGN KEY (`import_batch_id`) REFERENCES `roster_import_batch` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `followup_task` ADD CONSTRAINT `fk_followup_task_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `followup_task` ADD CONSTRAINT `fk_followup_task_node_definition_id`
  FOREIGN KEY (`node_definition_id`) REFERENCES `followup_node_definition` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `followup_task_participant` ADD CONSTRAINT `fk_followup_task_participant_task_id`
  FOREIGN KEY (`task_id`) REFERENCES `followup_task` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `followup_task_confirmation` ADD CONSTRAINT `fk_followup_task_confirmation_task_id`
  FOREIGN KEY (`task_id`) REFERENCES `followup_task` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `communication_record` ADD CONSTRAINT `fk_communication_record_followup_task_id`
  FOREIGN KEY (`followup_task_id`) REFERENCES `followup_task` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `communication_record` ADD CONSTRAINT `fk_communication_record_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `communication_text_version` ADD CONSTRAINT `fk_communication_text_version_communication_id`
  FOREIGN KEY (`communication_id`) REFERENCES `communication_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `ai_summary_version` ADD CONSTRAINT `fk_ai_summary_version_communication_id`
  FOREIGN KEY (`communication_id`) REFERENCES `communication_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `risk_assessment` ADD CONSTRAINT `fk_risk_assessment_ai_summary_version_id`
  FOREIGN KEY (`ai_summary_version_id`) REFERENCES `ai_summary_version` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `risk_assessment` ADD CONSTRAINT `fk_risk_assessment_communication_id`
  FOREIGN KEY (`communication_id`) REFERENCES `communication_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `probation_review` ADD CONSTRAINT `fk_probation_review_followup_task_id`
  FOREIGN KEY (`followup_task_id`) REFERENCES `followup_task` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `probation_review` ADD CONSTRAINT `fk_probation_review_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `probation_review` ADD CONSTRAINT `fk_probation_review_communication_id`
  FOREIGN KEY (`communication_id`) REFERENCES `communication_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `regularization_record` ADD CONSTRAINT `fk_regularization_record_ai_summary_version_id`
  FOREIGN KEY (`ai_summary_version_id`) REFERENCES `ai_summary_version` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `regularization_record` ADD CONSTRAINT `fk_regularization_record_probation_review_id`
  FOREIGN KEY (`probation_review_id`) REFERENCES `probation_review` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `regularization_record` ADD CONSTRAINT `fk_regularization_record_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `separation_record` ADD CONSTRAINT `fk_separation_record_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `separation_checklist_item` ADD CONSTRAINT `fk_separation_checklist_item_separation_record_id`
  FOREIGN KEY (`separation_record_id`) REFERENCES `separation_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `hr_confirmation_item` ADD CONSTRAINT `fk_hr_confirmation_item_employee_id`
  FOREIGN KEY (`employee_id`) REFERENCES `employee` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `hr_confirmation_item` ADD CONSTRAINT `fk_hr_confirmation_item_employment_id`
  FOREIGN KEY (`employment_id`) REFERENCES `employment_record` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `roster_import_row` ADD CONSTRAINT `fk_roster_import_row_batch_id`
  FOREIGN KEY (`batch_id`) REFERENCES `roster_import_batch` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `roster_import_issue` ADD CONSTRAINT `fk_roster_import_issue_batch_id`
  FOREIGN KEY (`batch_id`) REFERENCES `roster_import_batch` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `roster_import_issue` ADD CONSTRAINT `fk_roster_import_issue_row_id`
  FOREIGN KEY (`row_id`) REFERENCES `roster_import_row` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `roster_import_operation` ADD CONSTRAINT `fk_roster_import_operation_batch_id`
  FOREIGN KEY (`batch_id`) REFERENCES `roster_import_batch` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE `roster_import_operation` ADD CONSTRAINT `fk_roster_import_operation_row_id`
  FOREIGN KEY (`row_id`) REFERENCES `roster_import_row` (`id`)
  ON DELETE RESTRICT ON UPDATE CASCADE;

-- ================================================================
-- 索引补充（非外键索引已在 CREATE TABLE 中包含）
-- ================================================================
