# 员工生命周期管理系统

单公司内部使用的员工生命周期管理系统，管理员工从入职、试用期、跟进、转正、异动到离职的全过程。

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.x（同步）+ Alembic + SQLite
- **前端**：Vue 3 + TypeScript + Vite + Vue Router + Pinia
- **依赖管理**：uv（后端）、npm（前端）

## 快速开始

### 后端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 文档

参见 `docs/` 目录。
