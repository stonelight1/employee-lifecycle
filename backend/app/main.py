"""FastAPI 主应用"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
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
)

app = FastAPI(
    title="员工生命周期管理系统 API",
    version="0.4.0",
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


# === 异常处理器 ===

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=_status_code_for(exc),
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


@app.get("/api/health")
async def health_check():
    return {"success": True, "data": {"status": "ok", "version": "0.3.0"}}
