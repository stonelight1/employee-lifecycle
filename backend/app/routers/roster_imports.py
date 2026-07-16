"""花名册导入路由。"""

from __future__ import annotations

import json
import logging
import uuid
from io import BytesIO
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from ..config import settings

logger = logging.getLogger(__name__)
from ..deps import get_current_user, get_db_session
from ..enums import (
    ConfirmationIssueCode,
    ResolutionStatus,
    RosterBatchStatus,
    RosterRowStatus,
)
from ..exceptions import ResourceNotFound, ValidationError
from ..models.roster_batch import RosterImportBatch
from ..models.roster_issue import RosterImportIssue
from ..models.roster_row import RosterImportRow
from ..schemas.common import ApiResponse, PageParams
from ..schemas.roster_import import (
    BatchListResponse,
    BatchResolveRequest,
    BatchResolveResponse,
    ColumnAliasItem,
    CommitConfirmation,
    CommitResponse,
    CreateColumnAliasRequest,
    CreateValueAliasRequest,
    FieldDefinition,
    IssueItem,
    PreviewResponse,
    PreviewSummary,
    ResolveIssueRequest,
    RollbackPreviewResponse,
    RosterUploadResponse,
    SaveMappingRequest,
    SaveMappingResponse,
    ValueAliasItem,
)
from ..services.hr_confirmation_service import (
    confirm_item as hr_confirm_item,
    sync_roster_issues_to_confirmations,
)
from ..services.operation_log_service import create_log
from ..services.roster_commit_service import commit_import
from ..services.roster_import_service import list_batches
from ..services.roster_issue_resolution import (
    batch_resolve_issues,
    get_handler,
    needs_recalc,
    resolve_issue,
)
from ..services.roster_issue_recommendation import (
    AUTO_FIXABLE_ISSUE_CODES,
    enrich_issue_list,
    enrich_issue_with_recommendation,
)
from ..services.roster_repair_service import revalidate_batch, execute_repair
from ..services.roster_mapping_service import (
    auto_detect_mappings,
    create_column_alias,
    create_value_alias,
    get_field_definitions,
    list_column_aliases,
    list_value_aliases,
    normalize_header,
    save_mapping,
)
from ..services.roster_parser import (
    _detect_sheet,
    detect_sheet_names,
    parse_excel,
    save_uploaded_file,
)
from ..services.normalize import normalize_name
from ..services.benefit_parser import parse_benefit_text
from ..services.roster_preview_service import generate_preview
from ..services.roster_rollback_service import execute_rollback, preview_rollback

router = APIRouter(tags=["花名册导入"])


def _default_roster_storage() -> Path:
    database_url = settings.database_url
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///")).parent / "roster_imports"
    return Path("data") / "roster_imports"


ROSTER_STORAGE = _default_roster_storage()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}

DATE_FIELD_KEYS = {
    "birth_date", "hire_date", "expected_hire_date",
    "regularization_date", "separation_date", "contract_end_date",
    "social_insurance_start_date", "housing_fund_start_date",
}
EXCEL_DATE_EPOCH = date(1899, 12, 30)


# ============================================================
# 上传与批次管理
# ============================================================


@router.post(
    "/roster-imports/upload",
    response_model=ApiResponse[RosterUploadResponse],
    summary="上传花名册文件",
)
async def upload_roster(
    file: UploadFile = File(..., description="Excel 文件 (.xlsx / .xlsm)，最大 20MB"),
    mode: str = Form(default="SYNC", description="导入模式: SYNC / INITIALIZE"),
    sheet_name: str | None = Form(default=None, description="指定工作表"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """上传花名册 Excel 文件，创建导入批次，自动检测字段映射。"""
    # --- 文件校验 ---
    if not file.filename:
        raise ValidationError("文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"不支持的文件类型 '{ext}'，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
        )

    if ext == ".xls":
        raise ValidationError("请将文件另存为 .xlsx 格式后再上传")

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"文件大小超过 20MB 限制（当前 {file_size / 1024 / 1024:.1f}MB）"
        )

    if file_size == 0:
        raise ValidationError("文件不能为空")

    # --- 计算 SHA-256 ---
    import hashlib
    sha256_hash = hashlib.sha256(content).hexdigest()

    # --- 检查重复文件（仅 SUCCEEDED 禁止重复） ---
    existing_batch = (
        db.query(RosterImportBatch)
        .filter(
            RosterImportBatch.file_sha256 == sha256_hash,
            RosterImportBatch.batch_status == RosterBatchStatus.SUCCEEDED.value,
        )
        .order_by(RosterImportBatch.id.desc())
        .first()
    )
    if existing_batch:
        return {
            "success": True,
            "data": {
                "batch_id": existing_batch.id,
                "batch_no": existing_batch.batch_no,
                "file_name": file.filename,
                "file_size": file_size,
                "file_sha256": sha256_hash,
                "sheet_names": [],
                "selected_sheet": None,
                "header_row": 0,
                "total_rows": 0,
                "status": _enum_value(existing_batch.batch_status),
                "message": f"该文件已经于{existing_batch.completed_at.strftime('%Y年%m月%d日') if existing_batch.completed_at else ''}导入",
                "suggestion": "duplicate_batch",
            },
            "request_id": str(uuid.uuid4()),
        }

    # --- 保存到本地存储 ---
    upload_buffer = BytesIO(content)
    upload_buffer.filename = file.filename
    saved_file = save_uploaded_file(upload_buffer, str(ROSTER_STORAGE))
    stored_path = saved_file["stored_path"]

    try:
        # --- 检测工作表 ---
        sheet_names = detect_sheet_names(stored_path)

        # --- 选择工作表（优先"员工花名册-总表"）---
        if sheet_name:
            selected_sheet = sheet_name
        else:
            selected_sheet = _detect_sheet(sheet_names)

        # --- 解析 ---
        parse_result = parse_excel(stored_path, sheet_name=selected_sheet)
        header_row_index = parse_result.get("header_row", 1)
        total_rows = len(parse_result.get("rows", []))
        message = "文件已上传并完成表头识别"
        suggestion = None

        # --- 创建批次记录 ---
        batch = _create_batch_record(
            db=db,
            file_name=file.filename,
            stored_path=stored_path,
            file_size=file_size,
            file_sha256=sha256_hash,
            mode=mode,
            sheet_name=selected_sheet,
            header_row_index=header_row_index,
            total_rows=total_rows,
        )

        # --- 自动检测字段映射 ---
        detected_mappings = auto_detect_mappings(parse_result.get("headers", []))
        if detected_mappings:
            save_mapping(
                db,
                batch.id,
                detected_mappings,
                current_user.get("user_id", "system"),
            )

        create_log(
            db,
            operator_id=current_user.get("user_id", "system"),
            object_type="ROSTER_IMPORT",
            object_id=batch.id,
            operation_type="UPLOAD",
            after_data={
                "batch_id": batch.id,
                "file_name": file.filename,
                "mode": mode,
                "sheet_name": selected_sheet,
            },
        )

        db.commit()

        return {
            "success": True,
            "data": {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "file_name": file.filename,
                "file_size": file_size,
                "file_sha256": sha256_hash,
                "sheet_names": sheet_names,
                "selected_sheet": selected_sheet,
                "header_row": header_row_index,
                "total_rows": total_rows,
                "status": _enum_value(batch.batch_status),
                "message": message,
                "suggestion": suggestion,
            },
            "request_id": str(uuid.uuid4()),
        }
    except Exception:
        # 清理本次产生的临时文件
        import os as _os
        try:
            if _os.path.isfile(stored_path):
                _os.remove(stored_path)
        except Exception:
            pass
        raise


@router.get(
    "/roster-imports",
    response_model=ApiResponse[BatchListResponse],
    summary="花名册导入批次列表",
)
def list_batches_route(
    params: PageParams = Depends(),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    items, total = list_batches(db, page=params.page, page_size=params.page_size)
    return {
        "success": True,
        "data": {"items": items, "total": total},
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 单个批次
# ============================================================


@router.get(
    "/roster-imports/{batch_id}",
    response_model=ApiResponse[dict],
    summary="获取批次详情",
)
def get_batch_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")

    data = _batch_to_dict(batch)
    data["column_mappings"] = _column_mappings_from_batch(batch)
    data["mappings"] = data["column_mappings"]
    data["current_mappings"] = {
        item["source_header"]: item["target_field_key"]
        for item in data["column_mappings"]
        if item["target_field_key"]
    }

    return {
        "success": True,
        "data": data,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 行列表
# ============================================================


@router.get(
    "/roster-imports/{batch_id}/rows",
    response_model=ApiResponse[dict],
    summary="批次行列表",
)
def list_rows_route(
    batch_id: int,
    status: str | None = Query(default=None, description="行状态筛选（兼容旧参数）"),
    import_action: str | None = Query(default=None, description="导入动作: NEW/UPDATE/UNCHANGED/SKIP"),
    review_status: str | None = Query(default=None, description="审核状态: CLEAN/NEEDS_CONFIRMATION/ERROR/RESOLVED/IGNORED"),
    execution_status: str | None = Query(default=None, description="执行状态: PENDING/IMPORTED/FAILED/SKIPPED"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    query = db.query(RosterImportRow).filter(RosterImportRow.batch_id == batch_id)

    # 兼容旧参数
    if status:
        query = query.filter(RosterImportRow.row_status == status)
    if import_action:
        query = query.filter(RosterImportRow.import_action == import_action)
    if review_status:
        query = query.filter(RosterImportRow.review_status == review_status)
    if execution_status:
        query = query.filter(RosterImportRow.execution_status == execution_status)

    # 待确认筛选：只要任一新状态或旧状态为 NEEDS_CONFIRMATION
    if status == "NEEDS_CONFIRMATION":
        query = query.filter(
            or_(
                RosterImportRow.review_status == "NEEDS_CONFIRMATION",
                RosterImportRow.row_status == "NEEDS_CONFIRMATION",
            )
        )

    total = query.count()
    rows = (
        query.order_by(RosterImportRow.row_no.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "data": {
            "items": [_row_to_dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 问题列表
# ============================================================


@router.get(
    "/roster-imports/{batch_id}/issues",
    response_model=ApiResponse[dict],
    summary="批次问题列表",
)
def list_issues_route(
    batch_id: int,
    severity: str | None = Query(default=None, description="严重级别: BLOCKER / WARNING"),
    status: str | None = Query(default=None, description="处理状态: PENDING / RESOLVED / IGNORED / DEFERRED"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    query = db.query(RosterImportIssue).filter(RosterImportIssue.batch_id == batch_id)

    if severity:
        query = query.filter(RosterImportIssue.severity == severity)
    if status:
        query = query.filter(RosterImportIssue.resolution_status == status)

    issues = query.order_by(RosterImportIssue.severity.asc(), RosterImportIssue.id.asc()).all()

    # 统计各状态数量
    pending_count = sum(1 for i in issues if i.resolution_status == "PENDING")
    resolved_count = sum(1 for i in issues if i.resolution_status == "RESOLVED")
    ignored_count = sum(1 for i in issues if i.resolution_status == "IGNORED")

    # 转换为字典并添加推荐信息
    issue_dicts = [_issue_to_dict(i) for i in issues]
    enriched = enrich_issue_list(issue_dicts)

    return {
        "success": True,
        "data": {
            "items": enriched,
            "total": len(issues),
            "pending_count": pending_count,
            "resolved_count": resolved_count,
            "ignored_count": ignored_count,
        },
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 字段映射
# ============================================================


@router.post(
    "/roster-imports/{batch_id}/mapping",
    response_model=ApiResponse[SaveMappingResponse],
    summary="保存字段映射",
)
def save_mapping_route(
    batch_id: int,
    body: SaveMappingRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    save_mapping(
        db, batch_id, body.mappings,
        current_user.get("user_id", "system"),
    )
    batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")
    _sync_batch_rows_from_mapping(db, batch, body.mappings)

    result = {
        "batch_id": batch_id,
        "mapped_count": sum(1 for value in body.mappings.values() if value),
        "unmapped_count": sum(1 for value in body.mappings.values() if not value),
        "unmapped_required": [],
    }

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="SAVE_MAPPING",
        after_data={"mapped_count": result.get("mapped_count")},
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 预览
# ============================================================


@router.post(
    "/roster-imports/{batch_id}/preview",
    response_model=ApiResponse[PreviewResponse],
    summary="生成导入预览",
)
def preview_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    result = generate_preview(db, batch_id)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="PREVIEW",
        after_data={"summary": result.get("summary")},
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 问题处理
# ============================================================


@router.patch(
    "/roster-imports/{batch_id}/issues/{issue_id}",
    response_model=ApiResponse[IssueItem],
    summary="处理导入问题",
)
def resolve_issue_route(
    batch_id: int,
    issue_id: int,
    body: ResolveIssueRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """处理/解决单个导入问题。

    动作映射规则：
    - MODIFY_VALUE → 修改字段值，重置行状态，需重新预览
    - MAP_VALUE → 映射组织字典，重置行状态，需重新预览
    - SELECT_EMPLOYEE → 选择已有员工，重置行状态，需重新预览
    - CREATE_NEW_EMPLOYEE → 创建新员工，重置行状态，需重新预览
    - CONFIRM_REEMPLOYMENT → 确认重新入职，重置行状态，需重新预览
    - SKIP_ROW → 跳过整行
    - IGNORE → 忽略（仅 WARNING）
    - DEFER → 推迟处理

    未知动作 → 拒绝。
    BLOCKER 级别问题不能 IGNORE 或仅 ACCEPT。
    """
    issue = (
        db.query(RosterImportIssue)
        .filter(RosterImportIssue.id == issue_id, RosterImportIssue.batch_id == batch_id)
        .first()
    )
    if not issue:
        raise ResourceNotFound(f"导入问题不存在: {issue_id}")

    allowed = _parse_json_list(issue.allowed_actions_json)
    if allowed and body.action not in allowed:
        raise ValidationError(
            f"操作 '{body.action}' 不被允许，允许的操作: {', '.join(allowed)}"
        )

    # 检查处理器是否存在
    handler = get_handler(body.action)
    if handler is None:
        raise ValidationError(
            f"不支持的问题处理动作: {body.action}"
        )

    # 执行处理
    resolve_issue(db, issue, body.action, body.value, body.note, current_user)

    # 如果动作触发了数据修改，需要重新预览该行
    if needs_recalc(body.action) and issue.row_id:
        # 标记批次需要重新预览
        batch = (
            db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
        )
        if batch and batch.batch_status == RosterBatchStatus.READY.value:
            batch.batch_status = RosterBatchStatus.PREVIEW_READY

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="RESOLVE_ISSUE",
        after_data={"issue_id": issue_id, "action": body.action},
    )

    db.commit()

    return {
        "success": True,
        "data": _issue_to_dict(issue),
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/roster-imports/{batch_id}/issues/batch-resolve",
    response_model=ApiResponse[BatchResolveResponse],
    summary="批量处理问题",
)
def batch_resolve_route(
    batch_id: int,
    body: BatchResolveRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """批量处理问题（单一事务）。

    支持的操作：
    - APPLY_RECOMMENDATION: 批量应用推荐处理（仅 auto_fixable=True 的问题）
    - IGNORE: 批量忽略（仅 WARNING 级别）

    事务规则：
    - 所有操作在单一事务中执行
    - 任何异常导致整批回滚
    - 数据变化导致冲突时返回冲突列表，不启动事务
    """
    if body.action not in ("APPLY_RECOMMENDATION", "IGNORE"):
        raise ValidationError(
            f"不支持的批量操作: {body.action}。支持: APPLY_RECOMMENDATION, IGNORE"
        )

    result = batch_resolve_issues(
        db=db,
        batch_id=batch_id,
        issue_ids=body.issue_ids,
        action=body.action,
        note=body.note,
        operator=current_user,
        auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
    )

    if result.get("conflicts"):
        # 有冲突时返回冲突信息，不提交
        db.rollback()
        return {
            "success": True,
            "data": result,
            "request_id": str(uuid.uuid4()),
        }

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="BATCH_RESOLVE_ISSUES",
        after_data={
            "action": body.action,
            "total": result.get("total"),
            "resolved": result.get("resolved"),
        },
    )

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 提交导入
# ============================================================


@router.post(
    "/roster-imports/{batch_id}/commit",
    response_model=ApiResponse[CommitResponse],
    summary="提交导入",
)
def commit_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """提交批次导入，执行员工的新增/更新操作（幂等）。

    如果提交失败，使用独立事务保存 FAILED 状态。
    """
    from sqlalchemy.orm import Session as NewSession

    try:
        result = commit_import(db, batch_id, current_user)

        # 操作日志
        create_log(
            db,
            operator_id=current_user.get("user_id", "system"),
            object_type="ROSTER_IMPORT",
            object_id=batch_id,
            operation_type="COMMIT",
            after_data=result,
        )

        db.commit()

        return {
            "success": True,
            "data": result,
            "request_id": str(uuid.uuid4()),
        }
    except Exception:
        db.rollback()

        # 使用独立事务保存 FAILED 状态
        try:
            engine = db.get_bind()
            fail_session = NewSession(bind=engine)
            try:
                batch = fail_session.query(RosterImportBatch).filter(
                    RosterImportBatch.id == batch_id,
                ).first()
                if batch:
                    batch.batch_status = RosterBatchStatus.FAILED
                    batch.failed_at = datetime.now()
                    batch.failure_message = "导入执行失败，所有业务数据已回滚"
                    fail_session.commit()
            finally:
                fail_session.close()
        except Exception as inner_e:
            logger.error(
                "保存 FAILED 状态失败: batch_id=%s error=%s",
                batch_id, inner_e, exc_info=True,
            )

        raise


# ============================================================
# 撤销
# ============================================================


@router.get(
    "/roster-imports/{batch_id}/rollback-preview",
    response_model=ApiResponse[RollbackPreviewResponse],
    summary="预览撤销",
)
def rollback_preview_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    result = preview_rollback(db, batch_id)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/roster-imports/{batch_id}/rollback",
    response_model=ApiResponse[CommitResponse],
    summary="执行撤销",
)
def rollback_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    result = execute_rollback(db, batch_id, current_user)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="ROLLBACK",
        after_data=result,
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 重新校验与修复
# ============================================================


@router.post(
    "/roster-imports/{batch_id}/revalidate",
    response_model=ApiResponse[dict],
    summary="重新校验导入批次",
)
def revalidate_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """重新校验已成功导入的批次。

    读取原始花名册数据，比对系统当前状态，生成差异报告。
    默认只检查不修改数据。
    """
    result = revalidate_batch(db, batch_id)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="REVALIDATE",
        after_data={"stats": result.get("stats")},
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/roster-imports/{batch_id}/repair",
    response_model=ApiResponse[dict],
    summary="执行批次修复",
)
def repair_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """执行批次自动修复。

    修复失败时整批回滚。
    """
    result = execute_repair(db, batch_id, current_user)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="REPAIR",
        after_data=result,
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 同步待确认事项
# ============================================================


@router.post(
    "/roster-imports/{batch_id}/sync-confirmations",
    response_model=ApiResponse[dict],
    summary="同步待确认事项（将已有导入问题转为 HR 确认事项）",
)
def sync_confirmations_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """将已成功导入批次中未处理的导入问题同步为 HR 确认事项。

    功能：
    - 只处理状态为 SUCCEEDED 的批次
    - 使用稳定幂等键防止重复创建
    - 无法转换的问题（无员工、无映射）返回原因
    - 不修改已经正确的业务数据

    重复调用保持幂等。
    """
    result = sync_roster_issues_to_confirmations(db, batch_id)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=batch_id,
        operation_type="SYNC_CONFIRMATIONS",
        after_data=result,
    )

    db.commit()

    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 文件下载
# ============================================================


@router.get(
    "/roster-imports/{batch_id}/file",
    summary="下载原始文件",
)
def download_file_route(
    batch_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")

    stored_path = Path(batch.stored_file_path)
    if not stored_path.exists():
        raise ResourceNotFound(f"文件不存在: {batch.stored_file_path}")

    return FileResponse(
        path=str(stored_path),
        filename=batch.file_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================
# 字段定义 / 别名管理
# ============================================================


@router.get(
    "/roster-imports/field-definitions",
    response_model=ApiResponse[list[FieldDefinition]],
    summary="系统字段定义列表",
)
def field_definitions_route(
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    definitions = get_field_definitions()
    return {
        "success": True,
        "data": definitions,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/roster-imports/column-aliases",
    response_model=ApiResponse[list[ColumnAliasItem]],
    summary="列别名列表",
)
def list_column_aliases_route(
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    aliases = list_column_aliases(db)
    return {
        "success": True,
        "data": aliases,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/roster-imports/column-aliases",
    response_model=ApiResponse[ColumnAliasItem],
    status_code=201,
    summary="创建列别名",
)
def create_column_alias_route(
    body: CreateColumnAliasRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    alias = create_column_alias(
        db,
        {
            "source_header": body.source_header_normalized,
            "target_field_key": body.target_field_key,
            "created_by": current_user.get("user_id", "system"),
        },
    )

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=alias.id,
        operation_type="CREATE_COLUMN_ALIAS",
        after_data={
            "source_header_normalized": body.source_header_normalized,
            "target_field_key": body.target_field_key,
        },
    )

    db.commit()

    return {
        "success": True,
        "data": alias,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/roster-imports/value-aliases",
    response_model=ApiResponse[list[ValueAliasItem]],
    summary="值别名列表",
)
def list_value_aliases_route(
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    aliases = list_value_aliases(db)
    return {
        "success": True,
        "data": aliases,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/roster-imports/value-aliases",
    response_model=ApiResponse[ValueAliasItem],
    status_code=201,
    summary="创建值别名",
)
def create_value_alias_route(
    body: CreateValueAliasRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    alias = create_value_alias(
        db,
        {
            "field_key": body.field_key,
            "source_value": body.source_value_normalized,
            "target_value": body.target_value,
            "created_by": current_user.get("user_id", "system"),
        },
    )

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=alias.id,
        operation_type="CREATE_VALUE_ALIAS",
        after_data={
            "field_key": body.field_key,
            "source_value_normalized": body.source_value_normalized,
            "target_value": body.target_value,
        },
    )

    db.commit()

    return {
        "success": True,
        "data": alias,
        "request_id": str(uuid.uuid4()),
    }


# ============================================================
# 内部辅助函数
# ============================================================


def _create_batch_record(
    db: DBSession,
    file_name: str,
    stored_path: str,
    file_size: int,
    file_sha256: str,
    mode: str,
    sheet_name: str | None,
    header_row_index: int,
    total_rows: int,
):
    batch_no = f"RI-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"

    batch = RosterImportBatch(
        batch_no=batch_no,
        mode=mode,
        file_name=file_name,
        stored_file_path=str(stored_path),
        file_sha256=file_sha256,
        file_size=file_size,
        sheet_name=sheet_name,
        header_row=json.dumps({"index": header_row_index}),
        header_row_index=header_row_index,
        total_rows=total_rows,
        batch_status="UPLOADED",
    )
    db.add(batch)
    db.flush()
    return batch


def _batch_to_dict(batch) -> dict:
    header = {}
    try:
        header = json.loads(batch.header_row) if batch.header_row else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "mode": _enum_value(batch.mode),
        "file_name": batch.file_name,
        "stored_file_path": batch.stored_file_path,
        "file_sha256": batch.file_sha256,
        "file_size": batch.file_size,
        "sheet_name": batch.sheet_name,
        "header_row": header,
        "header_row_index": batch.header_row_index if hasattr(batch, "header_row_index") else None,
        "batch_status": _enum_value(batch.batch_status),
        "total_rows": batch.total_rows,
        "new_count": batch.new_count,
        "update_count": batch.update_count,
        "unchanged_count": batch.unchanged_count,
        "confirmation_count": batch.confirmation_count,
        "warning_count": batch.warning_count,
        "error_count": batch.error_count,
        "skipped_count": batch.skipped_count,
        "imported_count": batch.imported_count,
        "started_at": str(batch.started_at) if batch.started_at else None,
        "completed_at": str(batch.completed_at) if batch.completed_at else None,
        "failed_at": str(batch.failed_at) if batch.failed_at else None,
        "failure_message": batch.failure_message,
        "rolled_back_at": str(batch.rolled_back_at) if batch.rolled_back_at else None,
        "created_at": str(batch.created_at) if hasattr(batch, "created_at") and batch.created_at else None,
        "updated_at": str(batch.updated_at) if hasattr(batch, "updated_at") and batch.updated_at else None,
    }


def _column_mappings_from_batch(batch: RosterImportBatch) -> list[dict]:
    field_defs = {field["key"]: field for field in get_field_definitions()}
    mappings = _parse_mapping_items(batch.header_row)
    detected_mappings = auto_detect_mappings(
        [item["header"] for item in mappings if item.get("header")]
    )

    result = []
    for item in mappings:
        header = item.get("header")
        if not header:
            continue
        target = item.get("field_key") or detected_mappings.get(header)
        field_def = field_defs.get(target or "")
        result.append(
            {
                "source_header": header,
                "source_header_normalized": normalize_header(header),
                "target_field_key": target,
                "is_mapped": bool(target),
                "is_required": bool(field_def and field_def.get("required")),
                "is_unknown": not bool(target),
                "save_as_alias": False,
            }
        )
    return result


def _parse_mapping_items(header_row_json: str | None) -> list[dict[str, str | None]]:
    if not header_row_json:
        return []
    try:
        data = json.loads(header_row_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, list):
        result = []
        for item in data:
            if isinstance(item, dict) and "header" in item:
                result.append({"header": str(item["header"]), "field_key": item.get("field_key")})
        return result
    return []


def _sync_batch_rows_from_mapping(
    db: DBSession,
    batch: RosterImportBatch,
    mappings: dict[str, str | None],
) -> None:
    if not batch.stored_file_path:
        return

    parse_result = parse_excel(batch.stored_file_path, sheet_name=batch.sheet_name)
    rows = parse_result.get("rows", [])
    if not rows:
        return

    existing_by_row_no = {
        row.row_no: row
        for row in db.query(RosterImportRow)
        .filter(RosterImportRow.batch_id == batch.id)
        .all()
    }

    for index, raw_row in enumerate(rows, start=1):
        normalized_data = _normalize_import_row(raw_row, mappings)
        name = str(normalized_data.get("name") or "").strip()
        normalized_name = normalize_name(name) if name else ""

        row = existing_by_row_no.get(index)
        if row is None:
            row = RosterImportRow(batch_id=batch.id, row_no=index, normalized_name=normalized_name)
            db.add(row)

        row.normalized_name = normalized_name
        row.raw_data_json = json.dumps(raw_row, ensure_ascii=False, default=str)
        row.normalized_data_json = json.dumps(normalized_data, ensure_ascii=False, default=str)
        row.row_status = "NEW"
        row.diff_json = None
        row.planned_actions_json = None
        row.result_json = None

    batch.total_rows = len(rows)
    db.flush()


def _normalize_import_row(
    raw_row: dict,
    mappings: dict[str, str | None],
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for source_header, target_field in mappings.items():
        if not target_field:
            continue
        value = raw_row.get(source_header)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        normalized[target_field] = _normalize_mapped_value(target_field, value)

    if "benefit_raw_text" in normalized:
        normalized.update(
            parse_benefit_text(
                normalized.get("benefit_raw_text"),
                actual_hire_date=normalized.get("hire_date"),
                actual_regularization_date=normalized.get("regularization_date"),
            )
        )
    return normalized


def _normalize_mapped_value(field_key: str, value: object) -> object:
    if field_key in DATE_FIELD_KEYS:
        parsed = _parse_excel_date_value(value)
        if parsed:
            return parsed.isoformat()
    return value


def _parse_excel_date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 1 <= value <= 2958465:
        try:
            return EXCEL_DATE_EPOCH + timedelta(days=int(value))
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


def _row_to_dict(row) -> dict:
    def _safe_json(val):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "row_no": row.row_no,
        "employee_id": row.employee_id,
        "normalized_name": row.normalized_name,
        "match_type": _enum_value(row.match_type),
        "row_status": _enum_value(row.row_status),
        "import_action": _enum_value(row.import_action) if hasattr(row, "import_action") else None,
        "review_status": _enum_value(row.review_status) if hasattr(row, "review_status") else None,
        "execution_status": _enum_value(row.execution_status) if hasattr(row, "execution_status") else None,
        "raw_data": _safe_json(row.raw_data_json),
        "normalized_data": _safe_json(row.normalized_data_json),
        "diff": _safe_json(row.diff_json),
        "planned_actions": _safe_json(row.planned_actions_json),
        "result": _safe_json(row.result_json),
        "lifecycle_decision": _safe_json(row.lifecycle_decision_json) if hasattr(row, "lifecycle_decision_json") else None,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def _issue_to_dict(issue) -> dict:
    def _safe_json(val):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    employee_name = None
    row_no = None
    if hasattr(issue, 'row') and issue.row:
        employee_name = getattr(issue.row, 'normalized_name', None)
        row_no = getattr(issue.row, 'row_no', None)

    return {
        "id": issue.id,
        "batch_id": issue.batch_id,
        "row_id": issue.row_id,
        "employee_id": issue.employee_id,
        "field_key": issue.field_key,
        "issue_code": issue.issue_code,
        "severity": _enum_value(issue.severity),
        "title": issue.title,
        "message": issue.message,
        "old_value": _safe_json(issue.old_value_json),
        "new_value": _safe_json(issue.new_value_json),
        "allowed_actions": _safe_json(issue.allowed_actions_json) or [],
        "resolution_status": _enum_value(issue.resolution_status),
        "resolution_action": issue.resolution_action,
        "resolution_value_json": _safe_json(issue.resolution_value_json),
        "resolution_note": issue.resolution_note,
        "resolved_at": str(issue.resolved_at) if issue.resolved_at else None,
        "created_at": str(issue.created_at) if issue.created_at else None,
        "updated_at": str(issue.updated_at) if issue.updated_at else None,
        "employee_name": employee_name,
        "row_no": row_no,
    }


def _parse_json_list(val: str | None) -> list:
    if not val:
        return []
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return parsed
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _prefer_static_routes() -> None:
    """确保 /roster-imports/field-definitions 等静态路由先于 /{batch_id} 匹配。"""
    router.routes.sort(key=lambda route: ("{" in getattr(route, "path", ""), getattr(route, "path", "")))


_prefer_static_routes()
