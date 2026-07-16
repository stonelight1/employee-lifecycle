# 08 部署与环境配置

> 版本：v0.4.2  
> 最后更新：2026-07-16

## 1. 已确认技术栈

后端：

- Python 3.12。
- FastAPI。
- Pydantic v2。
- SQLAlchemy 2.x 同步 ORM。
- Alembic。
- SQLite。
- uv + `pyproject.toml` + `uv.lock`。
- pytest。

前端：

- Vue 3。
- TypeScript。
- Vite。
- Vue Router。
- Pinia。
- npm + `package-lock.json`。

访问模式：

- 单用户。
- 无登录、JWT、Session、角色和权限认证。
- 默认本机或受信任内网访问。

## 2. 部署目标

- 单公司内部使用，一名 HR 操作。
- 员工规模不超过 100 人。
- 优先单机部署、低成本和易维护。
- 不引入微服务、消息集群或复杂分布式组件。
- 不安装 ffmpeg、语音 SDK、本地语音模型或其他 ASR 依赖。
- 不将无认证的应用直接暴露到公网。

## 3. 推荐目录

```text
project-root/
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   └── src/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   └── tests/
├── data/
├── logs/
├── docs/
├── AGENTS.md
├── .env.example
└── .env
```

真实 `.env`、SQLite 数据库、日志和备份不得提交版本库。

## 4. 环境变量

至少配置：

```dotenv
APP_ENV=development
APP_DEBUG=true
APP_HOST=127.0.0.1
APP_PORT=8000

DATABASE_URL=sqlite:///./data/employee_lifecycle.db
LOG_LEVEL=INFO
LOG_DIR=./logs

LOCAL_OPERATOR_ID=1
LOCAL_OPERATOR_NAME=LOCAL_HR

CORS_ORIGINS=http://localhost:5173
COMMUNICATION_TEXT_MAX_LENGTH=50000

AI_ENABLED=false
AI_PROVIDER=
AI_BASE_URL=
AI_MODEL=
AI_API_KEY=
AI_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=2
AI_DAILY_LIMIT=0
AI_MONTHLY_LIMIT=0
```

不得再配置或读取：

- JWT 密钥。
- Session 密钥。
- Token 过期时间。
- 默认管理员账号和密码。
- 角色或权限初始化配置。

## 5. 单用户操作者

- `LOCAL_OPERATOR_ID` 和 `LOCAL_OPERATOR_NAME` 只用于审计显示。
- 后端创建、修改、确认、审核和日志动作统一使用该配置。
- 前端不得提交操作者身份。
- 修改显示名称不会改变历史数据；如需统一修改历史显示，应通过明确迁移完成。

## 6. SQLite 配置

默认数据库：

```text
./data/employee_lifecycle.db
```

要求：

- 启动连接执行 `PRAGMA foreign_keys = ON`。
- 数据目录持久化且应用进程可读写。
- 不放在临时目录。
- 不启动多个独立后端实例同时写同一 SQLite 文件。
- 迁移和重要发布前备份。
- 建议设置合理的 busy timeout，避免短时写锁直接失败。

## 7. 数据库迁移

使用 Alembic：

```bash
cd backend
uv run alembic current
uv run alembic upgrade head
uv run alembic downgrade -1
```

生成迁移草稿：

```bash
uv run alembic revision --autogenerate -m "change description"
```

规则：

1. 自动生成后必须人工检查。
2. 每个迁移实现 `upgrade()` 和 `downgrade()`。
3. SQLite 表结构调整按需使用 batch mode。
4. 建唯一索引前检查重复数据。
5. 删除认证表、外键或字段前先确认没有业务依赖。
6. 迁移前备份 SQLite。

本版本认证清理重点：

- 不新增用户、角色、权限、会话和令牌表。
- 若已有认证路由但无数据库表，只删除代码依赖。
- 若已有未上线认证表，确认无依赖后通过迁移删除。
- 审计字段保留并改由固定本地操作者写入。

## 8. 启动命令

后端安装和启动：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端安装和开发启动：

```bash
cd frontend
npm install
npm run dev
```

前端生产构建：

```bash
cd frontend
npm ci
npm run build
```

测试：

```bash
cd backend
uv sync --extra dev
uv run pytest

cd ../frontend
npm install
npm run test
```

若前端尚未配置 `test` 脚本，应以实际 `package.json` 为准，不得伪造已执行测试。

## 9. 访问安全

### 9.1 本机使用

推荐后端监听：

```text
127.0.0.1:8000
```

前端和后端仅本机访问，这是无认证模式的默认方案。

### 9.2 内网使用

需要从另一台内网电脑访问时：

- 后端监听受信任内网地址。
- 防火墙仅允许指定内网网段或设备。
- CORS 只配置实际前端地址。
- 不做公网端口映射。

### 9.3 远程访问

必须通过以下任一外部保护：

- VPN。
- 公司安全网关。
- 带登录认证的反向代理。
- 零信任访问代理。

不得直接把 FastAPI 端口暴露到公网。

## 10. AI 配置和降级

- `AI_ENABLED=false` 时前端禁用生成按钮并显示明确原因。
- 后端返回 `AI_NOT_CONFIGURED`，不得返回模糊 500。
- AI 密钥只从服务端环境变量读取。
- 日志不打印密钥和完整沟通文本。
- AI 不可用时员工、任务、沟通、人工风险、转正和离职仍可使用。
- AI 接口虽然无登录鉴权，但必须校验沟通记录和文本版本归属。

## 11. 生产部署建议

适合本项目的方式：

- 一台 HR 本地电脑直接运行。
- 或部署在公司现有内网服务器。
- 前端构建为静态文件。
- 后端使用单实例进程。
- SQLite、日志和备份使用持久化目录。

不推荐：

- Kubernetes。
- 消息队列集群。
- 多实例共享 SQLite 写入。
- 直接公网开放。
- 为单用户重新建设登录权限系统。

## 12. 备份和恢复

最低要求：

- 每日自动备份 SQLite。
- 重要发布和迁移前手工备份。
- 备份文件名包含日期、时间和版本。
- 定期验证恢复。
- 备份目录仅本机用户或受信任运维账号可访问。

恢复步骤：

1. 停止应用写入。
2. 备份当前异常数据库。
3. 恢复指定备份。
4. 检查数据库完整性和 Alembic 版本。
5. 启动应用。
6. 验证员工、任务、沟通、文本版本和日志。

## 13. 日志和健康检查

日志至少包含：

- 应用启动和停止。
- 数据库迁移结果。
- 定时任务结果。
- 业务异常代码和 `request_id`。
- AI 调用状态、耗时和失败类型。
- 固定本地操作者执行的关键业务动作。

日志不得包含：

- AI 密钥。
- 完整沟通文本。
- 不必要的手机号、邮箱和身份数据。

健康检查至少验证：

- 应用进程可用。
- SQLite 可连接并启用外键。
- 必要表和 Alembic 版本存在。
- AI 配置状态可读取。

健康检查不验证登录和权限，因为 V1 不存在认证功能。

## 14. 发布检查

- [ ] 后端使用 Python 3.12、FastAPI、SQLAlchemy 2.x 和 Alembic。
- [ ] 前端使用 Vue 3、TypeScript 和 Vite。
- [ ] uv 和 npm 锁文件已提交。
- [ ] `.env.example` 与代码读取变量一致。
- [ ] `.env`、SQLite、日志和备份未提交。
- [ ] 登录、Token、角色、权限和认证中间件已移除。
- [ ] 固定本地操作者已生效。
- [ ] 默认监听地址和防火墙不会直接暴露公网。
- [ ] CORS 未配置任意来源。
- [ ] 迁移前备份完成。
- [ ] AI 关闭和失败降级已验证。
- [ ] 无 ffmpeg、ASR SDK 或语音模型依赖。
- [ ] 健康检查和数据库恢复验证通过。
