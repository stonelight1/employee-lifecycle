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
from sqlalchemy.orm import Session as DBSession

from ..config import settings

logger = logging.getLogger(__name__)
from ..deps import get_current_user, get_db_session
from ..enums import ResolutionStatus, RosterBatchStatus
from ..exceptions import ResourceNotFound, ValidationError
from ..models.roster_batch import RosterImportBatch
from ..models.roster_issue import RosterImportIssue
from ..models.roster_row import RosterImportRow
from ..schemas.common import ApiResponse, PageParams
from ..schemas.roster_import import (
    BatchListResponse,
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
from ..services.operation_log_service import create_log
from ..services.roster_commit_service import commit_import
from ..services.roster_import_service import list_batches
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

# Maximum upload file size: 20 MB
MAX_FILE_SIZE = 20 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}

DATE_FIELD_KEYS = {
    "birth_date",
    "hire_date",
    "expected_hire_date",
    "regularization_date",
    "separation_date",
    "contract_end_date",
    "social_insurance_start_date",
    "housing_fund_start_date",
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
        raise ValidationError(f"不支持的文件类型 '{ext}'，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    # 读取文件内容
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise ValidationError(f"文件大小超过 20MB 限制（当前 {file_size / 1024 / 1024:.1f}MB）")

    # --- 保存到本地存储 ---
    upload_buffer = BytesIO(content)
    upload_buffer.filename = file.filename
    saved_file = save_uploaded_file(upload_buffer, str(ROSTER_STORAGE))
    stored_path = saved_file["stored_path"]

    # --- 检测工作表 ---
    sheet_names = detect_sheet_names(stored_path)
    selected_sheet = sheet_name or (sheet_names[0] if sheet_names else None)

    # --- 解析表头与前几行（预览用） ---
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
        file_sha256=saved_file["sha256"],
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
            "file_sha256": saved_file["sha256"],
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
    """获取花名册导入批次列表（分页）。"""
    items, total = list_batches(db, page=params.page, page_size=params.page_size)

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
        },
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
    """获取单个花名册导入批次详情。"""
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
    status: str | None = Query(default=None, description="行状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取批次下的所有导入行（分页）。"""
    query = db.query(RosterImportRow).filter(RosterImportRow.batch_id == batch_id)

    if status:
        query = query.filter(RosterImportRow.row_status == status)

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
    status: str | None = Query(default=None, description="处理状态: PENDING / RESOLVED / IGNORED"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取批次导入过程中的所有问题。"""
    query = db.query(RosterImportIssue).filter(RosterImportIssue.batch_id == batch_id)

    if severity:
        query = query.filter(RosterImportIssue.severity == severity)
    if status:
        query = query.filter(RosterImportIssue.resolution_status == status)

    issues = query.order_by(RosterImportIssue.severity.asc(), RosterImportIssue.id.asc()).all()

    return {
        "success": True,
        "data": {
            "items": [_issue_to_dict(i) for i in issues],
            "total": len(issues),
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
    """保存批次列映射关系。"""
    save_mapping(
        db,
        batch_id,
        body.mappings,
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
    """解析 Excel 完整数据，匹配员工，生成导入预览。"""
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
    """处理/解决单个导入问题，更新问题状态。"""
    issue = (
        db.query(RosterImportIssue)
        .filter(RosterImportIssue.id == issue_id, RosterImportIssue.batch_id == batch_id)
        .first()
    )
    if not issue:
        raise ResourceNotFound(f"导入问题不存在: {issue_id}")

    # 验证允许的操作
    allowed = _parse_json_list(issue.allowed_actions_json)
    if allowed and body.action not in allowed:
        raise ValidationError(
            f"操作 '{body.action}' 不被允许，允许的操作: {', '.join(allowed)}"
        )

    # 更新问题
    issue.resolution_status = ResolutionStatus.RESOLVED
    issue.resolution_action = body.action
    issue.resolution_value_json = body.value
    issue.resolution_note = body.note
    issue.resolved_at = datetime.now()

    db.flush()

    # 检查是否所有 BLOCKER 都已处理 → 更新批次状态为 READY
    remaining_blockers = (
        db.query(RosterImportIssue)
        .filter(
            RosterImportIssue.batch_id == batch_id,
            RosterImportIssue.severity == "BLOCKER",
            RosterImportIssue.resolution_status == ResolutionStatus.PENDING,
        )
        .count()
    )

    if remaining_blockers == 0:
        batch = (
            db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
        )
        if batch and _enum_value(batch.batch_status) == RosterBatchStatus.WAITING_RESOLUTION.value:
            batch.batch_status = RosterBatchStatus.READY

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
    """提交批次导入，执行员工的新增/更新操作（幂等）。"""
    result = commit_import(db, batch_id, current_user)

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
    """预览撤销操作，列出可逆和不可逆操作。"""
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
    """执行撤销操作（幂等：已撤销则直接返回）。"""
    result = execute_rollback(db, batch_id)

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
    """下载上传的原始花名册文件。"""
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
    """获取系统可映射的字段定义列表。"""
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
    """获取所有列别名。"""
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
    """创建列别名（Excel 列名 -> 系统字段映射）。"""
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
        after_data={"source_header_normalized": body.source_header_normalized, "target_field_key": body.target_field_key},
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
    """获取所有值别名。"""
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
    """创建值别名（Excel 值 -> 系统值映射）。"""
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
    """创建 RosterImportBatch 记录并返回。"""
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
        total_rows=total_rows,
        batch_status="UPLOADED",
    )
    db.add(batch)
    db.flush()
    return batch


def _batch_to_dict(batch) -> dict:
    """将 RosterImportBatch ORM 对象转为字典。"""
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
    """将批次中保存的 header_row 映射 JSON 转为前端映射表行。"""
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
    """按当前映射把 Excel 行同步到 roster_import_row，供预览/提交使用。"""
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
    """将 RosterImportRow ORM 对象转为字典。"""
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
        "raw_data": _safe_json(row.raw_data_json),
        "normalized_data": _safe_json(row.normalized_data_json),
        "diff": _safe_json(row.diff_json),
        "planned_actions": _safe_json(row.planned_actions_json),
        "result": _safe_json(row.result_json),
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def _issue_to_dict(issue) -> dict:
    """将 RosterImportIssue ORM 对象转为字典。"""
    def _safe_json(val):
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

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
        "resolution_note": issue.resolution_note,
        "resolved_at": str(issue.resolved_at) if issue.resolved_at else None,
        "created_at": str(issue.created_at) if issue.created_at else None,
        "updated_at": str(issue.updated_at) if issue.updated_at else None,
    }


def _parse_json_list(val: str | None) -> list:
    """解析 JSON 数组字符串，失败时返回空列表。"""
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
