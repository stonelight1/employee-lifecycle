# 员工生命周期系统：完整花名册导入功能开发任务

> 仓库：`https://github.com/stonelight1/employee-lifecycle.git`  
> 目标：基于当前最新代码，一次性完成“完整员工花名册导入”，同时修正与最新业务规则冲突的旧逻辑。  
> 技术栈：FastAPI + SQLAlchemy + Alembic + SQLite；Vue 3 + TypeScript + Vite。  
> 使用场景：单公司、100 人以内、本地单机部署、单 HR 用户。  
> 本任务不要拆成多个版本，不要只做演示页面，不要使用 mock 数据冒充完成。

---

# 一、开始前必须做的事情

在修改代码前，完整阅读：

- `AGENTS.md`
- `docs/`
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/services/`
- `backend/app/routers/`
- `backend/app/enums.py`
- `backend/app/main.py`
- `backend/alembic/`
- `backend/tests/`
- `frontend/src/router/`
- `frontend/src/services/`
- `frontend/src/views/employee/`
- `frontend/src/views/dashboard/`
- `frontend/src/components/`

必须以当前实际代码为准，不允许根据本任务中的文件名猜测代码结构。文件名不一致时，在现有结构中选择最合理的位置。

开始前先执行现有测试和构建，记录基线结果：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run pytest

cd ../frontend
npm install
npm run build
```

如果当前已有失败项：

1. 先记录失败原因。
2. 判断是否由本任务修改引起。
3. 不要为了让测试变绿而删除测试或放宽正确的业务校验。

---

# 二、当前代码必须先修正的旧规则

当前代码中存在与已经确认的业务规则不一致的逻辑。花名册导入不能继续建立在这些旧逻辑上，本次必须一起修正。

## 2.1 员工姓名不可修改

当前员工更新逻辑仍允许修改姓名，必须改为：

- 员工创建后，普通编辑接口不能修改姓名。
- `EmployeeUpdate` 等普通 DTO 中删除姓名字段，或者后端收到姓名修改时明确拒绝。
- 标准化姓名作为员工匹配主键：
  - 去掉首尾空格。
  - 全角字符转半角。
  - 连续空白压缩为一个空格。
- 对未逻辑删除、未标记“录入错误”的员工，建立标准化姓名唯一约束。
- 同名员工不允许创建第二份正常档案。

姓名录错时：

1. 没有任何业务记录：允许删除错误档案后重新创建。
2. 已有业务记录：
   - 原档案标记为 `ENTRY_ERROR`（录入错误）。
   - 原档案只允许查看。
   - 不进入员工数量、在职、试用期、风险等统计。
   - 所有未完成任务和待办自动取消。
   - 历史记录保留。
   - HR重新创建正确员工档案。
3. 花名册导入不得自动修改姓名。
4. 姓名找不到，但身份证号或手机号与已有员工相同：
   - 只提示“可能是同一个人”。
   - 必须由 HR 确认。
   - 不自动合并，不自动改名。

## 2.2 待入职不能自动变成在职

当前到达入职日期后自动将 `PENDING` 改为 `ACTIVE` 的逻辑必须取消。

新规则：

- 预计入职日期只用于提醒。
- 到预计入职日后，员工仍然保持待入职。
- 页面显示“已超过预计入职日 N 天”。
- 每天继续提醒 HR。
- HR手动点击“确认入职”后才正式入职。
- 确认入职时：
  - 实际入职日期必填。
  - 默认今天。
  - 可以早于或晚于预计入职日期。
  - 不能晚于今天。
  - 保存预计入职日期和实际入职日期。
- 跟进任务、试用期结束日期、预计转正日期全部按实际入职日期计算。
- 人没有来时，HR可以修改预计入职日期或取消入职。
- 取消原因支持多选和补充说明。
- 已取消的待入职可以恢复：
  - 恢复后回到待入职。
  - 必须重新填写预计入职日期。
  - 以前的取消记录保留。

数据库和代码中要明确区分：

```text
expected_hire_date    预计入职日期
actual_hire_date      实际入职日期
```

不要继续让一个 `hire_date` 同时表示两种日期。

迁移现有数据时：

- `PENDING` 任职：原 `hire_date` 回填为 `expected_hire_date`，`actual_hire_date` 为空。
- `ACTIVE / SEPARATING / SEPARATED`：原 `hire_date` 回填为 `actual_hire_date`；如果没有更可靠的预计日期，可以同时回填到 `expected_hire_date`。
- 更新所有使用旧 `hire_date` 的查询、排序、试用期计算、时间线和页面。

## 2.3 试用期不能写死三个月

新规则：

- 所有人都有试用期。
- 默认 3 个月。
- 正式入职前可以设置 1～6 个月。
- 正式入职后不能修改试用期月数。
- 不支持延长试用期。
- 想提前结束试用期，使用“提前转正”。
- 试用期内换部门或岗位，不重新计算试用期。
- 预计转正日只提醒，不自动转正。
- 超过预计转正日后仍然保持试用中，并每天提醒 HR。
- HR只能选择：
  - 确认转正。
  - 试用期不通过。

新增或明确字段：

```text
probation_months
probation_start_date
probation_end_date
expected_regularization_date
actual_regularization_date
```

试用期结束日期按自然月计算：

- 同日原则。
- 目标月份没有同一天时，使用该月最后一天。
- 不能用固定 90 天代替 3 个月。

## 2.4 删除“延长试用期”业务入口

当前枚举和转正记录中仍有 `EXTENDED`。

本次要求：

- 前端不再显示延长试用期。
- 新接口不接受 `EXTENDED`。
- 服务层明确拒绝延长操作。
- 如果历史数据库已经存在 `EXTENDED`，只允许只读展示，不删除历史。
- 不要因为兼容历史记录而继续开放新的延长入口。

## 2.5 转正规则

HR点击转正时：

- 必须二次确认。
- 实际转正日期必填，默认今天。
- 实际转正日期：
  - 不能早于实际入职日期。
  - 不能晚于今天。
- 转正不能撤销。
- 不检查、不提示转正面谈或其他试用期任务是否完成。
- 所有未完成的试用期任务直接标记为 `COMPLETED`。
- 保存预计转正日期和实际转正日期。
- 允许以后修正“实际转正日期”，但：
  - 员工仍然保持已转正。
  - 必须填写修改原因。
  - 必须二次确认。
  - 保存修改前后日期。
- 提前转正由 HR直接操作，不需要审批。

## 2.6 试用期不通过和离职

试用期不通过：

- 原因必填。
- 原因支持多选和补充说明。
- 不直接变成已离职。
- 先进入“离职办理中”。
- 最后工作日必填。
- 未完成试用期任务自动取消。
- 到最后工作日后，由 HR手动确认离职。

普通员工和试用期员工主动辞职，都走相同离职流程。

离职清单至少包含：

- 工资。
- 社保。
- 公积金。
- 设备。
- 账号。

清单未完成时：

- 仍允许确认离职。
- 未完成事项继续提醒。
- 不能因为员工已经离职就自动消失。

“离职办理中”允许撤销：

- 必须填写原因。
- 恢复到进入离职前的状态。
- 已取消的任务不自动恢复。
- 历史记录保留。

正式确认离职后：

- 不允许撤销。
- 日期填错时允许修正实际离职日期。
- 修正时必须填写原因并二次确认。
- 员工状态仍然保持已离职。
- 员工回来时走再次入职。

## 2.7 再次入职

- 使用原员工档案。
- 新建一条新的任职记录。
- 重新计算试用期。
- 重新生成 7天、15天、30天、45天、转正面谈任务。
- 同一时间只能存在一条 `PENDING / ACTIVE / SEPARATING` 任职记录。
- 历史任职记录必须保留。

---

# 三、本次花名册格式

本次先适配工作表：

```text
员工花名册-总表
```

当前 Excel 的正式字段为 A～AK，共 37 列。

| Excel 列 | 表头 | 系统用途 |
|---|---|---|
| A | 空表头/序号 | 原始行号，仅用于追溯，不作为员工编号 |
| B | 地区 | 拆分为工作城市、办公方式或合作关系 |
| C | 是否在职 | 用于状态判断和提醒，不直接自动离职 |
| D | 用工形式 | 拆分员工类型、试用状态、办公方式 |
| E | 姓名 | 标准化姓名，员工主要匹配键 |
| F | 入职时间 | 首次初始化时作为实际入职日期；后续差异需确认 |
| G | 离职日期 | 只生成待离职确认，不自动离职 |
| H | 转正日期 | 实际转正日期或状态校验 |
| I | 部门 | 当前部门 |
| J | 分队 | 当前分队 |
| K | 岗位 | 当前岗位 |
| L | 合同状态 | 合同信息，只提醒确认，不自动修改 |
| M | 电话号码 | 手机号 |
| N | 身份证号 | 身份信息，变化时需 HR确认 |
| O | 性别 | 身份信息，变化时需 HR确认 |
| P | 年龄 | 仅用于校验，系统按出生日期计算 |
| Q | 出生日期 | 身份信息，变化时需 HR确认 |
| R | 银行卡号 | 多银行卡，新增需确认 |
| S | 开户银行 | 银行卡附属信息 |
| T | 支付宝账号 | 多支付宝账号，新增需确认 |
| U | 邮箱账号 | 邮箱 |
| V | 户籍 | 当前户籍并保留历史 |
| W | 居住地址 | 当前居住地址并保留历史 |
| X | 五险一金缴纳 | 拆分社保、公积金状态并保留历史 |
| Y | 户口类型 | 当前户口类型并保留历史 |
| Z | 毕业院校 | 教育信息并保留历史 |
| AA | 专业 | 教育信息并保留历史 |
| AB | 学历 | 教育信息并保留历史 |
| AC | 试用期（月） | 1～6个月；试用员工缺失时默认3个月 |
| AD | 空表头 | 实际含义为合同到期日期或“无固定期限” |
| AE | 签订公司 | 合同签订公司 |
| AF | 签订次数 | 只用于校验，系统按合同记录计算 |
| AG | 司龄 | 只用于校验，系统按任职历史计算 |
| AH | 备注 | 每次追加，不覆盖 |
| AI | 现底薪（默认含30%kpi） | 原文完整保存，并尝试结构化拆分 |
| AJ | MBTI | 文本或图片，多次测评记录 |
| AK | PDP | 文本或图片，多次测评记录 |

注意：

- 当前文件的 AJ 部分单元格写的是“图片”，但文件中不一定真的嵌入了图片。
- 如果只有“图片”两个字但没有真实图片，生成可忽略提醒，不允许编造图片。
- A 列没有正式表头，不作为员工编号。
- AD 列虽然没有表头，但根据上下文必须识别为“合同期限/合同到期日期”。
- Excel 后面多出的完全空白列、样式残留列不要创建业务字段，但原始行 JSON 中可以保留。

---

# 四、总体设计原则

## 4.1 两层保存

必须同时保存：

### 原始数据层

保存：

- 原始 Excel 文件。
- 文件 SHA-256。
- 工作表名称。
- 表头行。
- 原始列名。
- 每一行原始值。
- 公式文本。
- 公式缓存结果。
- 图片所在单元格和本地文件路径。
- 导入时间。
- 导入结果。
- 每条提醒及 HR处理结果。

目的：

> 任何时候都能知道 Excel 原来写了什么。

### 业务数据层

把数据分别写入：

- 员工核心档案。
- 员工扩展资料。
- 任职记录。
- 合同记录。
- 银行卡和支付宝账号。
- 薪酬记录。
- 社保、公积金记录。
- 教育信息。
- MBTI、PDP测评。
- 备注。
- 字段变更历史。
- HR待确认事项。
- 操作日志。

不要把整张表只塞进一个 JSON 后就算完成，也不要只新增几十个字段到 `employee` 表。

## 4.2 第一次初始化与后续同步分开

导入批次必须有模式：

```text
INITIALIZE    首次初始化
SYNC          后续同步
```

### INITIALIZE

用于第一次把现有员工搬进系统：

- 建立员工当前档案。
- 建立当前任职、合同、薪酬等现状。
- 不生成“调岗、调薪、换地址”等变化历史。
- 已经在职且入职日期不晚于今天的员工，可以直接初始化为 `ACTIVE`。
- 已经转正的员工直接初始化为 `REGULARIZED`。
- 仍在试用期的员工只生成今天之后还没有到期的任务。
- 已经过期任务不补生成。
- 已转正员工不生成试用期任务。
- 缺少入职日期时：
  - 仍然创建员工档案。
  - 标记“缺少入职日期”。
  - 不创建任职记录。
  - 不创建试用期任务。
- 初始化只是记录当前事实，不代表所有变化都发生在导入当天。

### SYNC

用于以后重复导入新花名册：

- 新员工按待入职/实际入职规则处理。
- 已存在员工只更新允许自动更新的字段。
- 需要确认的字段不自动修改。
- 产生异动、调薪、资料变更历史。
- Excel 中没有出现的现有员工不删除、不自动离职，只提醒 HR。
- 离职员工重新出现在花名册中，不自动恢复，提醒 HR是否再次入职。

系统第一次成功导入前，默认选择 `INITIALIZE`；以后默认 `SYNC`。允许 HR在上传页面看到当前模式，但不要让普通误操作随意再次执行初始化。再次初始化必须二次确认。

---

# 五、数据库设计

根据当前模型结构做最小但完整的扩展。表名可以根据现有命名规范调整，但职责不能丢失。

## 5.1 employee 表调整

保留核心字段，并增加或调整：

```text
employee_status:
- ACTIVE
- ARCHIVED
- ENTRY_ERROR

normalized_name:
- 对正常、未删除员工建立唯一约束

profile_completeness_status:
- COMPLETE
- INCOMPLETE
```

姓名普通更新接口必须禁用。

## 5.2 employee_profile

一名员工一条当前资料：

```text
id
employee_id                  UNIQUE
identity_card
gender
birth_date
household_registration
residence_address
household_type
graduation_school
major
education_level
social_insurance_status
housing_fund_status
created_at
updated_at
version
```

手机号和邮箱可以继续放在 `employee`，但所有变化要写历史。

身份证号不作为默认主键，只用于辅助识别和冲突提醒。

## 5.3 employment_record 调整

至少增加或明确：

```text
expected_hire_date
actual_hire_date
probation_months
probation_start_date
probation_end_date
expected_regularization_date
actual_regularization_date
employment_type
work_city
work_mode
team_name
status_before_separating
hire_cancelled_at
hire_cancel_reasons_json
hire_cancel_note
```

`employment_type` 建议：

```text
FORMAL
INTERN
OUTSOURCED
COOPERATION
OTHER
```

`work_mode` 建议：

```text
ONSITE
REMOTE
HYBRID
UNKNOWN
```

不能用“正式、试用、远程、外包”共用一个字段。

## 5.4 employee_attribute_history

用于保存普通字段变化：

```text
id
employee_id
employment_id                nullable
category
field_name
before_value_json
after_value_json
effective_date
source_type                  MANUAL / ROSTER_IMPORT
source_id
import_batch_id              nullable
operator_name
created_at
```

适合记录：

- 手机号。
- 邮箱。
- 居住地址。
- 户籍。
- 户口类型。
- 教育信息。
- 社保、公积金。
- 工作城市。
- 办公方式。
- 分队。
- 其他普通资料。

部门、岗位、直属负责人继续使用现有 `employment_change`，并扩展支持分队和工作地点，或者在不破坏现有接口的前提下统一到清晰的异动记录中。

## 5.5 employee_financial_account

同时支持银行卡和支付宝：

```text
id
employee_id
account_type                 BANK / ALIPAY
account_no
bank_name                    nullable
is_primary
status                       ACTIVE / INACTIVE
source_type
confirmed_at
created_at
updated_at
```

规则：

- 一个人可以有多张银行卡。
- 一个人可以有多个支付宝账号。
- 新账号不覆盖旧账号。
- HR确认后才新增。
- 可以设置一张工资卡和一个当前支付宝账号。
- Excel 没出现旧账号，不自动删除。

敏感字段在页面列表中默认遮挡中间内容，但详情页可由本地用户查看完整值。不要把真实账号写入程序日志文本。

## 5.6 employment_contract

```text
id
employee_id
employment_id
contract_status
signing_company
contract_type                 FIXED_TERM / INDEFINITE / UNKNOWN
start_date                    nullable
end_date                      nullable
signing_sequence
source_type
confirmed_at
created_at
updated_at
```

规则：

- 合同信息变化不自动更新。
- 合同签订公司变化不自动覆盖。
- HR确认后新增一条合同记录。
- 旧合同保留。
- “无固定期限”保存为 `INDEFINITE`，不要求到期日期。
- Excel签订次数只用于校验。
- 系统签订次数按合同记录自动计算。

## 5.7 compensation_record

```text
id
employee_id
employment_id
raw_salary_text
salary_type                  MONTHLY / DAILY / MIXED / UNKNOWN
base_salary
probation_salary
regular_salary
daily_rate
performance_amount
performance_ratio
commission_text
other_text
effective_date
source_type
import_batch_id
created_at
```

所有金额使用 `Decimal`，数据库使用定点小数，不允许使用浮点数。

规则：

- 原始“现底薪”文本必须完整保存。
- 能明确识别的数字才拆分。
- 例如：
  - `试用期7000，转正8000`
  - `2000+提成`
  - `150/天`
- 无法确定时：
  - 不猜测。
  - 保存原文。
  - 生成可忽略或可人工修正的提醒。
- 第二次以后底薪变化：
  - 更新当前薪酬显示。
  - 新增一条薪酬记录。
  - 不覆盖旧记录。
  - 没有明确调薪日期时，默认使用本次导入日期。

## 5.8 employee_assessment

```text
id
employee_id
assessment_type              MBTI / PDP
result_text
attachment_path              nullable
assessment_date              nullable
source_type
import_batch_id
created_at
```

规则：

- 可以保存多次结果。
- 最新一次显示在员工资料。
- 旧结果保留。
- 支持文字和真实图片。
- 单元格只有“图片”但文件中没有图片时，只生成提醒。

## 5.9 employee_note

```text
id
employee_id
employment_id                nullable
content
source_type
source_id
import_batch_id
source_row_no
content_hash
created_at
```

规则：

- 备注只追加，不覆盖。
- 同一个批次、同一行、同一内容不能重复创建。
- 重复导入同一文件不能重复生成备注。

## 5.10 organization_reference

用于管理导入中出现的部门、岗位、分队：

```text
id
reference_type               DEPARTMENT / POSITION / TEAM
name
normalized_name
enabled
created_at
updated_at
```

当前业务表可以继续保存名称字符串，避免一次性大改为外键，但导入时必须用该字典做校验。

新值出现时：

- 不直接创建。
- HR选择：
  - 新建。
  - 映射成已有值。
- 未处理前，该问题为阻断项。
- 映射选择要记住，下次自动识别。

## 5.11 roster_column_alias

保存列名别名：

```text
id
source_header_normalized
target_field_key
enabled
created_at
updated_at
```

默认识别示例：

```text
电话号码 / 手机号 / 手机号码 / 联系电话 / 电话 -> mobile
姓名 / 员工姓名 -> name
入职时间 / 入职日期 -> hire_date
```

第一次遇到陌生列名时让 HR选择一次，以后自动识别。

## 5.12 roster_value_alias

保存字段值映射：

```text
id
field_key
source_value_normalized
target_value
created_at
updated_at
```

适用于：

- 部门别名。
- 岗位别名。
- 分队别名。
- 用工形式别名。
- 在职状态别名。
- 五险一金描述别名。

## 5.13 roster_import_batch

```text
id
batch_no
mode                          INITIALIZE / SYNC
file_name
stored_file_path
file_sha256
file_size
sheet_name
header_row
status
total_rows
new_count
update_count
unchanged_count
confirmation_count
warning_count
error_count
skipped_count
imported_count
started_at
completed_at
failed_at
failure_message
rolled_back_at
created_at
updated_at
version
```

状态建议：

```text
UPLOADED
MAPPING_REQUIRED
PREVIEW_READY
WAITING_RESOLUTION
READY
IMPORTING
SUCCEEDED
FAILED
ROLLBACK_PREVIEW
ROLLED_BACK
```

## 5.14 roster_import_row

```text
id
batch_id
row_no
employee_id                  nullable
normalized_name
match_type
row_status
raw_data_json
normalized_data_json
diff_json
planned_actions_json
result_json
created_at
updated_at
```

`row_status`：

```text
NEW
UPDATE
UNCHANGED
NEEDS_CONFIRMATION
ERROR
SKIPPED
IMPORTED
```

## 5.15 roster_import_issue

```text
id
batch_id
row_id
employee_id                  nullable
field_key
issue_code
severity                      BLOCKER / WARNING
title
message
old_value_json
new_value_json
allowed_actions_json
resolution_status
resolution_action
resolution_value_json
resolution_note
resolved_at
created_at
updated_at
```

`resolution_status`：

```text
PENDING
RESOLVED
IGNORED
DEFERRED
```

## 5.16 hr_confirmation_item

用于导入完成后仍需 HR处理的事项，并显示在首页：

```text
id
employee_id
employment_id                nullable
source_type
source_id
issue_code
title
description
before_data_json
after_data_json
status                        PENDING / CONFIRMED / REJECTED / IGNORED
created_at
handled_at
```

例如：

- 合同变化。
- 新银行卡。
- 新支付宝。
- 身份证变化。
- 出生日期变化。
- 性别变化。
- 离职日期。
- 离职员工疑似再次入职。
- 缺少入职日期。
- 花名册未出现的系统员工。

HR可以：

- 确认。
- 拒绝。
- 忽略。

忽略后：

- 提醒消失。
- 不修改对应业务数据。
- 操作日志记录谁、何时、忽略了什么。

## 5.17 roster_import_operation

用于完整追溯和撤销：

```text
id
batch_id
row_id
employee_id
operation_type
target_table
target_id
before_snapshot_json
after_snapshot_json
reversible
irreversible_reason
created_at
```

所有新增、更新、历史记录创建都要保存操作快照。

## 5.18 separation_checklist_item

为已确认的离职规则补充：

```text
id
separation_record_id
item_type                     SALARY / SOCIAL_INSURANCE / HOUSING_FUND / DEVICE / ACCOUNT
title
completed
completed_at
remark
created_at
updated_at
```

员工已离职但清单未完成时，继续进入待办提醒。

---

# 六、Alembic 迁移要求

必须使用 Alembic，不允许启动时临时建表。

要求：

1. 新增全部表、字段、索引和唯一约束。
2. 使用 SQLite 兼容的 batch migration。
3. 正确迁移旧 `hire_date`。
4. 保留现有数据。
5. 提供完整 `upgrade()` 和 `downgrade()`。
6. `downgrade()` 不得静默丢失无法恢复的数据；如果确实无法无损降级，要在迁移说明中明确。
7. 检查并避免重复索引。
8. 至少建立：
   - 员工标准化姓名唯一索引。
   - 导入批次 SHA 索引。
   - 导入行批次+行号唯一索引。
   - 导入问题批次/状态索引。
   - 待确认事项状态索引。
   - 银行/支付宝员工索引。
   - 合同员工/任职索引。
   - 薪酬员工/任职/生效日期索引。
9. 迁移前说明如何备份本地 SQLite 文件。

必须实际执行：

```bash
cd backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

# 七、文件保存与 Git 规则

虽然系统只在本地使用，但 GitHub 仓库是代码仓库，真实花名册绝不能提交。

建议目录：

```text
backend/local_data/roster_imports/{batch_id}/original.xlsx
backend/local_data/employee_attachments/{employee_id}/...
backend/local_data/backups/...
```

必须更新 `.gitignore`：

```gitignore
backend/local_data/
backend/*.db
backend/**/*.db
*.sqlite
*.sqlite3
```

要求：

- 原文件名做安全处理，防止路径穿越。
- 保存真实文件名到数据库。
- 实际磁盘名使用 UUID。
- 不把身份证、银行卡、手机号等真实数据写进测试文件或 Git。
- 测试使用程序生成的虚拟 Excel。
- 不在异常日志中输出完整身份证号和银行卡号。
- 不把上传文件放进 `frontend/public/`。

---

# 八、Excel 读取和标准化

后端已经有 `openpyxl` 依赖，使用它完成 `.xlsx` 和 `.xlsm` 读取。

`.xls` 不支持时：

- 明确提示“请另存为 xlsx 后再上传”。
- 不要返回模糊的 500 错误。

## 8.1 上传限制

建议：

```text
允许：.xlsx / .xlsm
最大：20MB
默认工作表：员工花名册-总表
```

如果找不到默认工作表：

- 返回可选工作表列表。
- 让 HR选择。
- 允许选择表头行。

## 8.2 不依赖列顺序

- 按表头名称和别名识别。
- 列顺序变化不影响导入。
- 少列时只提示缺失字段。
- 多出未知列时：
  - 原始值仍保存。
  - 让 HR映射到已有字段，或标记为“仅保留原始数据”。
- 映射结果可以保存为列名别名。

## 8.3 姓名标准化

必须复用系统统一的姓名标准化方法，不允许导入模块自己再写一套不同规则。

Excel 同一批中出现两个相同标准化姓名：

- 两行都标记阻断错误。
- 不能通过“忽略”继续把两人导入成同一员工。

数据库中已经存在多个正常同名档案：

- 该员工行标记阻断错误。
- 要求先人工清理数据库。

## 8.4 日期解析

支持：

```text
Excel 日期对象
Excel 日期序号
2026-07-16
2026/7/16
2026.7.16
20260716
2026年7月16日
```

规则：

- 使用工作簿 epoch 正确解析 Excel 序号。
- 只有“7月16日”而没有年份时，不猜年份，生成问题。
- 非法日期不自动纠正。
- 日期统一保存为 date，不要因为时区变成前一天。
- 公式日期读取缓存结果。

## 8.5 公式

需要同时打开两份工作簿：

- `data_only=False`：读取公式。
- `data_only=True`：读取 Excel 上次保存的计算结果。

规则：

- 业务解析使用缓存结果。
- 原始层同时保存公式文本。
- 如果公式没有缓存值：
  - 生成提醒。
  - 不自己实现 Excel 公式计算器。
- 年龄和司龄最终仍由系统自己计算。

## 8.6 图片

读取锚定在单元格上的图片：

- 保存图片文件。
- 建立单元格坐标与图片路径关系。
- AJ/AK 图片写入测评记录。
- 一格多图时全部保存，并提示 HR选择主图。
- 图片读取失败时生成提醒。
- 不能只把“图片”两个字当作真实图片。

## 8.7 空白值

第一次导入：

- 空白保持为空。

后续导入：

- 空白不能清空系统已有值。
- 只有 HR在系统里手动删除，才允许清空。
- `无`、`/`、`-`、纯空格等要按字段定义判断：
  - 有些表示空。
  - 有些可能是业务值。
- 原始值始终保留。

## 8.8 文本清洗

统一处理：

- 首尾空格。
- 换行。
- 连续空白。
- 全角半角。
- 手机号中的空格和短横线。
- 身份证最后一位 `x/X`。
- 银行卡中的空格。
- 邮箱大小写。
- 不要删除备注中的正常换行。

---

# 九、员工匹配规则

匹配顺序：

## 9.1 第一优先：标准化姓名

- 找到一个正常员工：视为同一员工。
- 找不到：进入辅助识别。
- 找到多个：阻断错误。

## 9.2 辅助识别

只用于提示，不自动合并：

```text
身份证号相同
手机号相同
```

提示示例：

> 花名册中的“张小三”与系统“张三”的身份证号相同，可能是同一个人。

HR选择：

- 确认是同一个人：
  - 由于姓名不可直接修改，必须进入专门的姓名纠错流程。
  - 不允许导入模块偷偷改名。
- 不是同一个人：
  - 创建新员工。
- 稍后处理：
  - 本行可跳过或只保存原始数据，具体由 HR选择。

## 9.3 离职员工同名

系统中该姓名已经正式离职，而 Excel 又标记在职：

- 不自动恢复。
- 生成“可能再次入职”确认事项。
- HR确认后：
  - 使用原员工档案。
  - 新建任职记录。
  - 填写预计入职日期或实际入职日期。
  - 重新计算试用期和任务。
- HR认为 Excel 写错时可以忽略。

## 9.4 已逻辑删除员工

- 不自动恢复。
- 提醒 HR判断。
- 没有业务记录的错误档案可以走删除后重建。
- 有业务记录的档案按“录入错误”处理。

---

# 十、每个字段的更新规则

## 10.1 自动更新并保留历史

后续 `SYNC` 导入中，以下字段变化时自动更新：

- 手机号。
- 邮箱。
- 居住地址。
- 学历。
- 毕业院校。
- 专业。
- 户籍。
- 户口类型。
- 社保状态。
- 公积金状态。
- 工作城市。
- 办公方式。
- 分队。

要求：

- 更新当前值。
- 写入字段变化历史。
- Excel 为空时不清空原值。

## 10.2 不自动更新，只提醒 HR

以下变化不自动修改：

- 姓名。
- 身份证号。
- 出生日期。
- 性别。
- 合同状态。
- 合同签订公司。
- 合同期限。
- 银行卡。
- 支付宝账号。
- 离职状态。
- 再次入职。
- 已存在员工的实际入职日期。
- 新部门、新岗位、新分队映射。

HR可以：

- 确认。
- 拒绝。
- 忽略。
- 稍后处理。

## 10.3 部门、岗位、直属负责人、分队变化

`INITIALIZE`：

- 直接建立当前值。
- 不生成异动历史。

`SYNC`：

- 部门、岗位、直属负责人变化：
  - 自动生成异动记录。
  - 保存变更前后快照。
  - 来源为花名册导入。
- 分队变化：
  - 更新当前分队。
  - 保存分队调整记录。
- Excel 分队为空：
  - 不清空原分队。

如果出现系统从未见过的新部门、新岗位、新分队：

- 先让 HR选择“新建”或“映射已有值”。
- 未选择前不能执行该行的任职更新。
- 选择结果下次自动识别。

如果一个员工同一批中部门和岗位同时变化：

- 可以生成两条清晰的异动事件。
- 也可以生成一条包含两个字段的组合异动。
- 必须保证时间线清楚、前后值明确。
- 不允许只覆盖当前值而没有历史。

## 10.4 入职日期变化

系统已有实际入职日期与 Excel 不一致时：

- 不自动修改。
- 显示修改影响预览：
  - 预计转正日期。
  - 7/15/30/45天任务。
  - 转正面谈日期。
- HR确认后才修改。
- 已完成任务不修改。
- 未完成任务重新计算。
- 必须填写修改原因。
- 保存修改前后日期。

## 10.5 离职日期

Excel有离职日期：

- 不直接离职。
- 创建“待离职确认”事项。
- HR确认后走现有离职流程。
- 必须确认最后工作日。
- 最终离职仍由 HR手动确认。

Excel写“离职”但没有离职日期：

- 提醒 HR补日期。
- 不自动离职。

系统已离职但 Excel写“在职”：

- 提醒可能再次入职。
- 不自动恢复。

## 10.6 正式、试用、实习、外包、合作

必须拆开：

```text
员工类型：
- FORMAL
- INTERN
- OUTSOURCED
- COOPERATION

试用状态：
- NOT_STARTED
- IN_PROGRESS
- PENDING_REVIEW
- REGULARIZED
- FAILED
- TERMINATED

办公方式：
- ONSITE
- REMOTE
- HYBRID
```

当前表中的建议映射：

```text
正式          -> FORMAL + 已转正
试用          -> FORMAL + 试用中
实习          -> INTERN
大象外包      -> OUTSOURCED
淘金云合作    -> COOPERATION
远程          -> work_mode=REMOTE；员工类型根据其他字段判断，无法判断时让 HR确认
```

“地区”中的建议映射：

```text
北京 / 武汉   -> work_city
远程          -> work_mode=REMOTE
合作          -> 不作为城市；结合用工形式识别为合作关系
```

所有原始文本必须保留。

## 10.7 正式状态和转正日期冲突

表里写“正式”，但没有转正日期：

- 初始化时按已转正处理。
- 实际转正日期可以为空。
- 创建提醒，要求以后补充日期。
- 不要把员工重新当成试用期。

表里写“试用”，但填写了转正日期：

- 转正日期在未来：继续试用。
- 转正日期不晚于今天：按已转正处理。
- 创建“状态和日期不一致”提醒。

## 10.8 试用期月数

- 表里有 1～6：使用表中值。
- 试用员工为空：默认 3。
- 超出 1～6：阻断或要求 HR修正。
- 初始化时已经正式的老员工：
  - 直接标记已转正。
  - 不重新计算旧试用期。
- 后续正式入职后，不允许通过花名册修改试用期月数。

## 10.9 缺少入职日期

- 仍然创建员工档案和其他可保存资料。
- 标记资料不完整。
- 创建 HR提醒。
- 不创建任职记录。
- 不生成跟进任务。
- HR在系统补上日期后，再创建任职和任务。

## 10.10 年龄和司龄

年龄：

- 系统根据出生日期和当前日期计算。
- Excel 年龄只用于对照。
- 不一致时提醒。

司龄：

- 系统根据全部任职记录计算。
- 在职任职计算到今天。
- 已离职任职计算到实际离职日期。
- 再次入职时累计历史任职时长。
- Excel 司龄只用于对照。
- 日期格式、文本格式或明显异常值都不能直接写进系统司龄。

## 10.11 合同

- 合同任何变化都不自动修改。
- HR确认后新增合同记录。
- 旧合同保留。
- 无固定期限使用专门类型，不伪造到期日期。
- Excel签订次数与系统计算次数不一致时提醒。
- 不允许直接把“签订次数=3”当作三份真实合同。

## 10.12 五险一金

- 尽量拆分社保和公积金状态。
- 状态变化自动更新。
- 保留变化记录。
- 原文字段完整保存。
- 无法拆分时保存 `UNKNOWN` 和原文，并生成可忽略提醒。

## 10.13 银行卡和支付宝

- 不自动覆盖。
- 不自动删除旧账号。
- 新账号生成确认事项。
- HR确认后新增。
- 可设置当前工资卡或当前支付宝。
- 相同账号重复出现时保持幂等。

## 10.14 MBTI 和 PDP

- 文本保存文字。
- 真实图片保存附件。
- 多次结果保留。
- 最新结果显示在员工详情。
- PDP列中出现明显属于离职原因的内容，例如“自辞”：
  - 不自动当作 PDP。
  - 生成可忽略或可重新分类的提醒。
  - 原始值保留。

## 10.15 备注

- 每次导入作为一条新备注。
- 不覆盖旧备注。
- 保存来源、导入批次、行号、时间。
- 同一文件重复导入不能重复创建相同备注。

---

# 十一、任务生成规则

## 11.1 INITIALIZE

对于已经在职的老员工：

- 已转正：不生成试用期任务。
- 仍在试用：
  - 只生成今天之后的剩余节点。
  - 已经过期的7天、15天等节点不补生成。
- 缺少实际入职日期：不生成任务。

例如员工已经入职20天：

- 不生成7天、15天。
- 生成30天、45天、转正面谈。

## 11.2 SYNC中新员工

未来预计入职：

- 创建待入职任职。
- 不生成正式试用期任务。
- HR确认实际入职后生成任务。

花名册显示已在职且入职日在今天或以前：

- 不要仅凭日期静默入职。
- 生成“确认已实际入职”问题。
- HR在预览中明确确认后，可以在本次导入事务中创建 `ACTIVE` 任职。
- 任务按实际入职日期生成，只生成尚未过期的任务。

## 11.3 转正

HR确认转正后：

- 所有未完成试用期任务直接改为 `COMPLETED`。
- 不弹出“还有任务未完成”的警告。
- 不允许撤销转正。

---

# 十二、导入交互流程

员工列表页增加主按钮：

```text
导入花名册
```

新增页面：

```text
/roster-imports
/roster-imports/new
/roster-imports/:id
```

推荐步骤：

## 第一步：上传文件

展示：

- 文件选择。
- 导入模式。
- 工作表选择。
- 表头行。
- 上次使用的字段映射。
- 文件是否曾经导入。

同一个 SHA-256 文件已经成功导入时：

- 明确提醒“这个文件已经导入过”。
- 默认不允许再次提交相同业务操作。
- 可以重新打开历史导入详情。
- 如果 HR仍选择重新预览，必须保持幂等，不重复创建任何数据。

## 第二步：字段映射

展示：

```text
Excel列名 -> 系统字段
```

功能：

- 自动匹配。
- 手动修改。
- 未知列可选择“仅保留原始数据”。
- 保存别名。
- 显示必需字段是否缺失。

姓名必须映射。

## 第三步：导入预览

顶部汇总：

```text
新增员工
自动更新
需要确认
数据错误
无变化
本次未出现
```

每名员工展示：

- 姓名。
- 匹配到的系统员工。
- 当前状态。
- 变化字段。
- 原值。
- 新值。
- 系统准备执行的动作。
- 问题和提醒。

支持筛选：

- 全部。
- 新增。
- 更新。
- 待确认。
- 错误。
- 无变化。
- 跳过。

## 第四步：处理问题

每条问题按严重程度区分。

### BLOCKER

不能忽略，例如：

- 姓名为空。
- 同一 Excel 重复姓名。
- 数据库存在多个正常同名员工。
- 无法确定员工匹配。
- 试用期月数超出范围且未修正。
- 新部门/岗位/分队未映射。
- 文件结构损坏。

HR必须：

- 修改值。
- 选择映射。
- 跳过整行。
- 取消导入。

### WARNING

可以忽略，例如：

- 年龄对不上。
- 司龄对不上。
- 只有“图片”文字但没有真实图片。
- 薪资文本无法完全拆分。
- 正式员工缺少转正日期。
- 普通字段为空。
- PDP内容疑似填错列。

HR可以：

- 接受系统建议。
- 手工修改。
- 忽略。
- 稍后处理。

“忽略”必须写操作日志。

## 第五步：确认导入

确认弹窗展示：

```text
将新增多少人
将自动更新多少人
将创建多少条异动
将创建多少条薪酬记录
将新增多少条备注
将留下多少条待确认事项
将跳过多少行
```

HR二次确认后才提交。

## 第六步：结果页面

展示：

- 成功时间。
- 新增数量。
- 更新数量。
- 无变化数量。
- 跳过数量。
- 待确认数量。
- 每一行处理结果。
- 原始文件。
- 导入操作明细。
- 撤销入口。

---

# 十三、程序错误与数据问题

## 13.1 程序错误

例如：

- 数据库写入异常。
- 代码抛出异常。
- 文件在处理中损坏。
- 磁盘保存失败。
- 唯一约束意外冲突。

处理方式：

- 本次业务写入整批回滚。
- 一条员工数据都不能半成功。
- 批次标记为 `FAILED`。
- 错误信息单独事务保存。
- 原始上传文件和预览信息可以保留，便于排查。
- 页面明确显示“系统处理失败，本次没有写入业务数据”。

业务写入必须放在一个数据库事务中。

## 13.2 数据问题

数据问题不直接让程序崩溃。

处理方式：

- 先列出问题。
- HR做出选择。
- 所有阻断问题都有处理结果后，批次才变成 `READY`。
- HR可以明确跳过某一行。
- HR可以忽略普通提醒。
- 最终提交仍然是一个完整事务。

---

# 十四、导入提交的事务和幂等

## 14.1 预览阶段

预览阶段只允许写入：

- 导入批次。
- 原始文件。
- 原始行。
- 字段映射。
- 问题。
- HR解决方案。

不得修改员工业务数据。

## 14.2 提交阶段

提交阶段：

1. 锁定或乐观校验批次版本。
2. 确认状态为 `READY`。
3. 再次校验数据库数据是否在预览后发生变化。
4. 一个事务执行所有员工业务写入。
5. 每一步写 `roster_import_operation`。
6. 写操作日志。
7. 成功后批次改为 `SUCCEEDED`。
8. 任何异常全部回滚。
9. 回滚后用单独事务把批次改为 `FAILED`。

## 14.3 防止重复点击

- `commit` 接口必须幂等。
- 已成功批次再次提交时直接返回原结果。
- 正在导入时不能再次进入。
- 每条操作使用稳定幂等键，例如：

```text
batch_id + row_id + action_type + field_key
```

- 任务生成继续复用现有任务幂等键。
- 备注、异动、薪酬、确认事项均要防重复。

## 14.4 批量查询

禁止逐行产生大量 N+1 查询。

预览时一次批量加载：

- 所有姓名对应员工。
- 当前任职。
- 员工扩展资料。
- 当前合同。
- 财务账号。
- 当前薪酬。
- 组织字典。

员工只有100人以内，但仍应保持正确查询方式。

---

# 十五、整批撤销

每个成功导入批次提供“撤销导入”。

## 15.1 撤销预览

点击撤销前先展示：

- 会删除或标记删除的新增员工。
- 会恢复的字段。
- 会删除的导入历史记录。
- 不会撤销的 HR已确认事项。
- 已发生后续人工修改的冲突项。
- 已经产生其他业务记录的员工。

## 15.2 撤销规则

- 新增员工：
  - 没有后续业务记录时，可以逻辑删除。
  - 已经产生后续业务记录时，不直接删除，列为冲突并要求 HR处理。
- 自动更新字段：
  - 当前值仍等于本批次写入值时，恢复导入前值。
  - 当前值后来又被人工修改时，不覆盖人工修改，列为冲突。
- 导入创建的普通历史记录：
  - 没有被后续业务引用时撤销或逻辑删除。
- HR明确确认后创建的合同、银行卡、身份修正等：
  - 标记 `reversible=false`。
  - 不随整批撤销。
- 正式转正、正式离职等不可逆业务：
  - 不允许由花名册撤销功能反向修改。
- 撤销操作本身必须写操作日志。
- 撤销也要在一个事务中完成。
- 存在未处理冲突时，不允许只撤销一半；先让 HR处理冲突，再统一执行可撤销部分。
- 成功后批次状态为 `ROLLED_BACK`。
- 已撤销批次不能再次撤销。

---

# 十六、后端接口

根据现有路由风格实现，建议：

## 16.1 导入批次

```http
POST   /api/roster-imports/upload
GET    /api/roster-imports
GET    /api/roster-imports/{batch_id}
GET    /api/roster-imports/{batch_id}/rows
GET    /api/roster-imports/{batch_id}/issues
POST   /api/roster-imports/{batch_id}/mapping
POST   /api/roster-imports/{batch_id}/preview
PATCH  /api/roster-imports/{batch_id}/issues/{issue_id}
POST   /api/roster-imports/{batch_id}/commit
GET    /api/roster-imports/{batch_id}/rollback-preview
POST   /api/roster-imports/{batch_id}/rollback
GET    /api/roster-imports/{batch_id}/file
```

上传使用 `multipart/form-data`。

不要手工写死 multipart 的 `Content-Type`，让浏览器自动添加 boundary。

## 16.2 字段和别名

```http
GET    /api/roster-imports/field-definitions
GET    /api/roster-imports/column-aliases
POST   /api/roster-imports/column-aliases
GET    /api/roster-imports/value-aliases
POST   /api/roster-imports/value-aliases
```

## 16.3 HR待确认

```http
GET    /api/hr-confirmations
GET    /api/hr-confirmations/{id}
POST   /api/hr-confirmations/{id}/confirm
POST   /api/hr-confirmations/{id}/reject
POST   /api/hr-confirmations/{id}/ignore
```

接口操作必须调用对应业务服务，不允许只改提醒状态而不执行真实业务。

## 16.4 员工完整档案

扩展员工详情接口，或增加子接口：

```http
GET /api/employees/{id}/full-profile
GET /api/employees/{id}/contracts
GET /api/employees/{id}/financial-accounts
GET /api/employees/{id}/compensations
GET /api/employees/{id}/assessments
GET /api/employees/{id}/notes
GET /api/employees/{id}/attribute-history
```

## 16.5 生命周期修正接口

根据现有接口复用或补充：

```http
POST /api/employments/{id}/confirm-hire
POST /api/employments/{id}/cancel-hire
POST /api/employments/{id}/restore-hire
POST /api/employments/{id}/correct-actual-hire-date
POST /api/regularizations/{id}/correct-date
POST /api/separations/{id}/cancel
POST /api/separations/{id}/correct-date
```

不要建立两个功能重复的接口。优先检查现有实现后扩展。

---

# 十七、前端页面

## 17.1 导入记录列表

显示：

- 导入时间。
- 文件名。
- 模式。
- 状态。
- 新增。
- 更新。
- 跳过。
- 待确认。
- 操作：
  - 查看。
  - 下载原文件。
  - 撤销预览。
  - 撤销。

## 17.2 导入向导

必须是清晰的步骤式页面：

```text
1 上传文件
2 字段映射
3 数据预览
4 处理问题
5 确认导入
6 导入结果
```

不要把所有内容塞进一个很长的表单。

## 17.3 差异展示

每条变化显示：

```text
字段       当前值       Excel值       处理方式
手机号     138...       139...        自动更新
身份证号   420...       421...        需要确认
部门       客服部       销售部        自动生成异动
银行卡     尾号1234     尾号5678      确认后新增
```

身份号、银行卡在列表中遮挡中间部分。

## 17.4 问题处理

按钮根据问题类型显示：

```text
接受建议
修改
映射已有值
新建
稍后处理
忽略
跳过此员工
```

BLOCKER 不显示“忽略”。

## 17.5 首页待确认事项

在工作台增加“待确认事项”：

- 合同变化。
- 新银行卡。
- 新支付宝。
- 身份信息变化。
- 待离职。
- 疑似再次入职。
- 缺少入职日期。
- 花名册未出现员工。

显示数量和最紧急的几条，点击进入统一待确认列表。

## 17.6 员工详情

员工详情按分组展示完整资料：

```text
基本信息
身份与联系方式
户籍与地址
教育信息
当前任职
历史任职
合同
薪酬
银行卡与支付宝
社保与公积金
MBTI / PDP
备注
资料变化历史
```

要求：

- 当前信息一眼能看懂。
- 历史信息可以展开。
- 不直接显示原始 JSON。
- 不把37个字段挤进一张大表。
- 缺失字段显示 `—`。
- “资料不完整”员工显示明确提醒。

## 17.7 前端类型和服务

新增清晰类型：

```text
frontend/src/types/roster-import.ts
frontend/src/types/employee-profile.ts
frontend/src/types/hr-confirmation.ts
```

新增服务：

```text
frontend/src/services/rosterImportService.ts
frontend/src/services/hrConfirmationService.ts
```

核心数据禁止使用大量 `any`。

文件上传需要专门方法，不能被全局 JSON 请求头破坏。

---

# 十八、操作日志和时间线

导入相关关键动作全部记录：

```text
ROSTER_FILE_UPLOADED
ROSTER_MAPPING_SAVED
ROSTER_PREVIEW_GENERATED
ROSTER_ISSUE_RESOLVED
ROSTER_ISSUE_IGNORED
ROSTER_IMPORT_COMMITTED
ROSTER_IMPORT_FAILED
ROSTER_IMPORT_ROLLBACK_PREVIEWED
ROSTER_IMPORT_ROLLED_BACK
EMPLOYEE_CREATED_BY_ROSTER
EMPLOYEE_UPDATED_BY_ROSTER
EMPLOYMENT_CREATED_BY_ROSTER
CONTRACT_CONFIRMED_FROM_ROSTER
FINANCIAL_ACCOUNT_CONFIRMED_FROM_ROSTER
```

员工时间线展示有业务意义的事件：

- 花名册创建员工。
- 花名册更新联系方式。
- 部门/岗位/分队变化。
- 薪酬变化。
- 合同确认。
- 再次入职。
- 待离职确认。
- 导入撤销。

不要把纯技术事件全部塞进员工时间线。

---

# 十九、后端代码结构建议

根据当前项目结构实现，建议职责分开：

```text
backend/app/routers/roster_imports.py
backend/app/routers/hr_confirmations.py

backend/app/services/roster_import_service.py
backend/app/services/roster_parser.py
backend/app/services/roster_mapping_service.py
backend/app/services/roster_preview_service.py
backend/app/services/roster_commit_service.py
backend/app/services/roster_rollback_service.py
backend/app/services/hr_confirmation_service.py
backend/app/services/salary_parser.py

backend/app/schemas/roster_import.py
backend/app/schemas/hr_confirmation.py
backend/app/schemas/employee_profile.py
```

不要写一个数千行的 `roster_import_service.py` 包含所有事情。

解析、预览、业务写入、撤销必须分层。

`main.py` 注册新路由。

`models/__init__.py` 导出新模型，确保 Alembic 可以发现。

---

# 二十、测试要求

## 20.1 不使用真实花名册作为测试数据

禁止把用户真实 Excel 放进：

```text
backend/tests/fixtures/
frontend/public/
docs/
```

测试中用 `openpyxl` 动态生成虚拟花名册，字段结构与当前 A～AK 一致，但所有姓名、身份证、银行卡、手机号都使用虚构数据。

## 20.2 Excel解析测试

至少覆盖：

- 默认工作表存在。
- 默认工作表不存在。
- 表头行变化。
- 列顺序变化。
- 列名别名。
- 未知列。
- 空表头 A 和 AD 的识别。
- Excel日期对象。
- Excel序号。
- `YYYYMMDD`。
- 非法日期。
- 公式有缓存。
- 公式无缓存。
- 真图片。
- 只有“图片”文本。
- 尾部空格和全角字符。
- 空值、`无`、`/`。
- 薪酬常见格式。
- 薪酬无法解析。

## 20.3 员工匹配测试

至少覆盖：

- 新姓名。
- 已有同名。
- Excel内部重名。
- 数据库已有两个同名。
- 姓名不同但身份证相同。
- 姓名不同但手机号相同。
- 离职员工再次出现。
- 已逻辑删除员工。
- 录入错误员工。

## 20.4 INITIALIZE 测试

至少覆盖：

- 在职正式员工。
- 在职试用员工。
- 缺入职日期。
- 正式但无转正日期。
- 试用但转正日期已到。
- 已转正不生成任务。
- 入职20天只生成剩余任务。
- 第一次导入不生成异动和调薪历史。

## 20.5 SYNC 测试

至少覆盖：

- 自动更新手机号、邮箱、地址。
- 空白不清空旧值。
- 身份证变化只创建确认事项。
- 新银行卡不覆盖旧卡。
- 新支付宝不覆盖旧账号。
- 合同变化不自动修改。
- 部门变化生成异动。
- 岗位变化生成异动。
- 分队变化保留历史。
- 底薪变化新增薪酬记录。
- 备注追加且幂等。
- 花名册未出现的系统员工只提醒。
- 离职日期只进入待确认。
- 已离职员工疑似再次入职。

## 20.6 生命周期修正测试

至少覆盖：

- 到预计入职日不自动入职。
- 手动确认入职。
- 实际入职日期驱动任务日期。
- 试用期1～6个月。
- 正式入职后不能改试用期月数。
- 不允许延长试用期。
- 超过预计转正日不自动转正。
- 提前转正。
- 转正把未完成任务标记完成。
- 转正不可撤销。
- 试用期不通过进入离职办理中。
- 离职清单未完成仍可离职并继续提醒。
- 离职办理中可撤销。
- 正式离职不可撤销。
- 再次入职新建任职。
- 姓名不可普通修改。
- 录入错误档案不进入统计。

## 20.7 事务测试

必须通过故障注入测试：

- 第1行成功、第2行写入时故意抛异常。
- 验证第1行也没有写入业务表。
- 批次状态为失败。
- 原始文件和错误信息仍可查看。

## 20.8 幂等测试

- 同一文件重复上传。
- 同一批次重复预览。
- 同一批次重复提交。
- 提交接口并发点击。
- 重复备注。
- 重复异动。
- 重复任务。
- 重复银行卡确认。

## 20.9 撤销测试

- 撤销新增员工。
- 恢复自动更新字段。
- 人工后续修改产生冲突。
- HR确认的银行卡不撤销。
- 已产生业务记录的新员工不能直接删除。
- 撤销过程中异常整批回滚。
- 已撤销批次不能重复撤销。

## 20.10 前端测试

至少覆盖：

- 上传文件。
- 字段映射。
- 预览分类。
- BLOCKER不能忽略。
- WARNING可以忽略。
- 问题处理后汇总数量更新。
- 提交二次确认。
- 提交失败显示“未写入数据”。
- 导入历史。
- 撤销预览。
- 首页待确认事项。
- 员工详情完整字段分组。

如果当前已配置 Vitest，继续使用；如果没有完整脚本，补充：

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

---

# 二十一、实现顺序

必须按以下顺序开发，减少返工：

1. 修正姓名、待入职、试用期、转正、离职基础规则。
2. 完成 Alembic 数据模型迁移。
3. 完成员工完整档案、合同、财务账号、薪酬、测评等后端服务。
4. 完成 Excel 解析和字段映射。
5. 完成预览和问题分类。
6. 完成 HR问题处理。
7. 完成整批提交和幂等。
8. 完成导入历史和操作快照。
9. 完成撤销预览和撤销。
10. 完成后端测试。
11. 完成前端导入向导。
12. 完成首页待确认事项。
13. 完成员工详情完整资料展示。
14. 完成前端测试和构建。
15. 使用当前真实花名册在本地手工验收，但不要提交真实文件。

---

# 二十二、验收标准

必须全部满足：

## 数据完整性

- 当前 A～AK 所有字段都有明确去向。
- 未识别字段仍保留原始值。
- 原始 Excel 文件可以在导入记录中找到。
- 原始每行数据可查看。
- 真实图片可以保存。
- 空白不会错误清空旧数据。

## 匹配

- 姓名是主要唯一键。
- Excel重名会报错。
- 数据库同名冲突会报错。
- 身份证、手机号只用于辅助提醒。
- 不自动改名、不自动合并。

## 业务规则

- 待入职不再自动入职。
- 试用期不再写死3个月。
- 不允许延长试用期。
- 转正不可撤销。
- 试用期不通过进入离职办理中。
- 正式离职不可撤销。
- 再次入职使用原档案。
- 录入错误档案不参与统计。

## 导入流程

- 上传后先预览。
- 新增、更新、确认、错误、无变化分类正确。
- 普通提醒可以忽略。
- 阻断问题不能忽略。
- 程序错误时业务数据整批回滚。
- 数据问题可由 HR处理、忽略或跳过后继续。
- 同一文件重复导入不会重复写数据。
- 每次导入有完整记录。

## 更新规则

- 自动更新字段正确更新并留历史。
- 身份、合同、银行卡、支付宝不自动更新。
- 部门、岗位、分队变化保留异动。
- 薪资原文保留，金额使用 Decimal。
- 年龄和司龄由系统计算。
- 备注不覆盖且不重复。

## 撤销

- 可以查看撤销影响。
- 可逆操作能够恢复。
- HR已确认事项不撤销。
- 后续人工修改不会被覆盖。
- 撤销有完整操作日志。

## 页面

- 导入向导完整可用。
- 页面没有假按钮。
- 没有直接展示 JSON。
- 员工详情可以查看全部字段和历史。
- 首页可以处理待确认事项。
- 1024px 宽度下页面不明显错位。

## 构建与测试

必须执行成功：

```bash
cd backend
uv run alembic upgrade head
uv run pytest

cd ../frontend
npm run test
npm run build
```

---

# 二十三、禁止事项

- 不要只实现上传接口而没有预览、确认、历史和撤销。
- 不要把所有字段塞入一个 JSON 就宣称完成。
- 不要丢弃任何 Excel 列。
- 不要自动修改姓名、身份证、性别、出生日期。
- 不要自动覆盖银行卡、支付宝和合同。
- 不要因为 Excel 没有员工就自动离职。
- 不要因为到了日期就自动入职或自动转正。
- 不要继续支持延长试用期。
- 不要把程序异常当作某一行失败后继续写入。
- 不要逐员工产生 N+1 查询。
- 不要使用浮点数保存工资。
- 不要提交真实花名册、SQLite 数据库或员工附件到 Git。
- 不要在测试中使用真实员工数据。
- 不要用 `alert()`、`confirm()`、`prompt()` 代替正式交互组件。
- 不要保留点击无反应的按钮。
- 不要删除现有业务功能。
- 不要重构与本任务无关的大量代码。
- 不要只回复“已完成”，必须给出实际测试结果。

---

# 二十四、完成后必须输出

完成后请按以下顺序汇报：

1. 当前代码中修正了哪些旧业务规则。
2. 修改文件清单。
3. 新增文件清单。
4. 新增和修改的数据库表、字段、索引。
5. Alembic 迁移文件和回滚结果。
6. 当前37个Excel字段的最终映射。
7. 自动更新字段列表。
8. 需要 HR确认的字段列表。
9. 可忽略和不可忽略问题列表。
10. 导入批次状态机。
11. 员工匹配规则。
12. INITIALIZE 与 SYNC 的区别。
13. 程序错误时事务回滚实现。
14. 幂等实现。
15. 撤销实现和不能撤销的情况。
16. 新增后端接口。
17. 新增前端页面和路由。
18. 后端测试数量和结果。
19. 前端测试数量和结果。
20. 前端构建结果。
21. 使用虚拟 Excel 的验收结果。
22. 使用真实花名册本地验收时发现的问题，但不得输出真实个人数据。
23. 仍未完成或存在风险的事项。

禁止只输出笼统描述，必须明确列出命令执行结果和失败项。
