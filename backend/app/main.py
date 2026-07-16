"""FastAPI 主应用"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .logging_config import setup_logging

# 初始化日志（在创建 app 之前，确保启动阶段的日志被捕获）
setup_logging()
logger = logging.getLogger(__name__)

from .exceptions import (
    ActiveEmploymentExists,
    AiNotConfigured,
    AiResponseInvalid,
    AiSummaryFailed,
    AiSummaryOutdated,
    AiSummaryProcessing,
    AppException,
    CommunicationTextRequired,
    CommunicationTextTooLong,
    Conflict,
    DuplicateRequest,
    EmployeeMatchAmbiguous,
    FinalProbationReviewRequired,
    InvalidStateTransition,
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
    VersionConflict,
)
from .routers import (
    employees,
    employments,
    followup_nodes,
    followup_tasks,
    communications,
    ai_summaries,
    risk_assessments,
    probation,
    regularization,
    employment_changes,
    separation,
    todos,
    operation_logs,
    aggregate,
    roster_imports,
    hr_confirmations,
    employee_full_profile,
)

app = FastAPI(
    title="员工生命周期管理系统 API",
    version="0.4.2",
    description="Employee Lifecycle Management System",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 请求日志中间件 ===

@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.time() - start
        logger.exception(
            "未捕获异常 | method=%s path=%s duration=%.0fms request_id=%s",
            request.method,
            request.url.path,
            duration * 1000,
            getattr(request.state, "request_id", None),
        )
        raise

    duration = time.time() - start

    log_method = logger.info
    if response.status_code >= 500:
        log_method = logger.error
    elif response.status_code >= 400:
        log_method = logger.warning

    log_method(
        "%s %s -> %s  (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration * 1000,
    )
    return response


# === 启动日志 ===

@app.on_event("startup")
async def startup_log():
    logger.info("服务启动 | env=%s debug=%s", settings.app_env, settings.app_debug)
    logger.info("前端地址 : %s", settings.frontend_url)
    logger.info("已注册 17 个路由模块")


# === 异常处理器 ===

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    status_code = _status_code_for(exc)
    log_method = logger.error if status_code >= 500 else logger.warning
    log_method(
        "业务异常 | method=%s path=%s status=%s code=%s message=%s request_id=%s",
        request.method,
        request.url.path,
        status_code,
        exc.code,
        exc.message,
        getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def _status_code_for(exc: AppException) -> int:
    mapping = {
        ValidationError: 400,
        ResourceNotFound: 404,
        ResourceDeleted: 404,
        Conflict: 409,
        DuplicateRequest: 409,
        VersionConflict: 409,
        InvalidStateTransition: 409,
        EmployeeMatchAmbiguous: 409,
        ActiveEmploymentExists: 409,
        FinalProbationReviewRequired: 409,
        CommunicationTextRequired: 400,
        CommunicationTextTooLong: 400,
        AiNotConfigured: 503,
        AiSummaryProcessing: 409,
        AiSummaryFailed: 502,
        AiResponseInvalid: 502,
        AiSummaryOutdated: 409,
    }
    for exc_type, code in mapping.items():
        if isinstance(exc, exc_type):
            return code
    return 500


# === 路由 ===

app.include_router(employees.router, prefix="/api")
app.include_router(employments.router, prefix="/api")
app.include_router(followup_nodes.router, prefix="/api")
app.include_router(followup_tasks.router, prefix="/api")
app.include_router(communications.router, prefix="/api")
app.include_router(ai_summaries.router, prefix="/api")
app.include_router(risk_assessments.router, prefix="/api")
app.include_router(probation.router, prefix="/api")
app.include_router(regularization.router, prefix="/api")
app.include_router(employment_changes.router, prefix="/api")
app.include_router(separation.router, prefix="/api")
app.include_router(todos.router, prefix="/api")
app.include_router(operation_logs.router, prefix="/api")
app.include_router(aggregate.router, prefix="/api")
app.include_router(roster_imports.router, prefix="/api")
app.include_router(hr_confirmations.router, prefix="/api")
app.include_router(employee_full_profile.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"success": True, "data": {"status": "ok", "version": "0.4.2"}}
