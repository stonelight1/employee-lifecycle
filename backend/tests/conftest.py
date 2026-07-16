"""
测试基础设施 —— 内存 SQLite 数据库和通用 Fixture。

每个测试函数使用独立事务，测试结束后回滚。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.employee import Employee
from app.models.employment import EmploymentRecord
from app.models.followup_node import FollowupNodeDefinition
from app.models.followup_task import FollowupTask
from app.models.followup_participant import FollowupTaskParticipant, FollowupTaskConfirmation
from app.models.communication import CommunicationRecord
from app.models.text_version import CommunicationTextVersion
from app.models.ai_summary import AiSummaryVersion
from app.models.risk import RiskAssessment
from app.models.probation import ProbationReview
from app.models.regularization import RegularizationRecord
from app.models.change import EmploymentChange
from app.models.separation import SeparationRecord
from app.models.todo import SystemTodo
from app.models.operation_log import OperationLog


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """每个测试函数使用独立的内存 SQLite 数据库。"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def default_user() -> dict[str, str]:
    """默认测试用户。"""
    return {"user_id": "test-hr", "role": "HR_ADMIN"}


# ========== 工厂函数 ==========


def create_employee(
    db: Session,
    name: str = "张三",
    employee_no: str | None = "EMP001",
    employee_status: str = "ACTIVE",
    **kwargs: Any,
) -> Employee:
    emp = Employee(
        name=name,
        normalized_name=name.strip(),
        employee_no=employee_no,
        employee_status=employee_status,
        **kwargs,
    )
    db.add(emp)
    db.flush()
    return emp


def create_employment(
    db: Session,
    employee_id: int,
    hire_date: date | None = None,
    employment_status: str = "ACTIVE",
    probation_status: str = "IN_PROGRESS",
    probation_end_date: date | None = None,
    **kwargs: Any,
) -> EmploymentRecord:
    if hire_date is None:
        hire_date = date(2026, 7, 1)
    if probation_end_date is None:
        probation_end_date = date(2026, 10, 1)
    emp = EmploymentRecord(
        employee_id=employee_id,
        employment_seq=1,
        hire_date=hire_date,
        employment_status=employment_status,
        probation_status=probation_status,
        probation_end_date=probation_end_date,
        date_rule_source="AUTO",
        probation_end_date_source="AUTO",
        **kwargs,
    )
    db.add(emp)
    db.flush()
    return emp


def create_default_nodes(db: Session) -> list[FollowupNodeDefinition]:
    """创建默认 5 个跟进节点。"""
    nodes_data = [
        ("DAY_7", "入职后 7 天", "DAYS_AFTER_HIRE", 7, 1),
        ("DAY_15", "入职后 15 天", "DAYS_AFTER_HIRE", 15, 1),
        ("DAY_30", "入职后 30 天", "DAYS_AFTER_HIRE", 30, 1),
        ("DAY_45", "入职后 45 天", "DAYS_AFTER_HIRE", 45, 1),
        ("REG_INTERVIEW", "转正面谈", "REGULARIZATION_INTERVIEW", 0, 1),
    ]
    nodes = []
    for code, name, trigger, offset, version in nodes_data:
        node = FollowupNodeDefinition(
            node_code=code,
            node_name=name,
            trigger_type=trigger,
            offset_days=offset,
            enabled=True,
            confirmation_mode="ALL",
            node_version=version,
        )
        db.add(node)
        nodes.append(node)
    db.flush()
    return nodes


def create_task(
    db: Session,
    employment_id: int,
    node_definition_id: int | None = None,
    task_name: str = "测试任务",
    followup_status: str = "PENDING",
    planned_date: date | None = None,
    offset_days_snapshot: int = 7,
    **kwargs: Any,
) -> FollowupTask:
    if planned_date is None:
        planned_date = date(2026, 7, 8)
    task = FollowupTask(
        employment_id=employment_id,
        node_definition_id=node_definition_id,
        node_version=1,
        node_code_snapshot=task_name,
        task_name=task_name,
        task_source="AUTO",
        trigger_type_snapshot="DAYS_AFTER_HIRE",
        offset_days_snapshot=offset_days_snapshot,
        planned_date=planned_date,
        original_planned_date=planned_date,
        date_adjusted_manually=False,
        followup_status=followup_status,
        confirmation_mode="ALL",
        idempotency_key=f"task_{employment_id}_{node_definition_id}_{offset_days_snapshot}",
        **kwargs,
    )
    db.add(task)
    db.flush()
    return task


def create_communication(
    db: Session,
    employment_id: int,
    followup_task_id: int | None = None,
    communication_status: str = "COMPLETED",
    **kwargs: Any,
) -> CommunicationRecord:
    comm = CommunicationRecord(
        employment_id=employment_id,
        followup_task_id=followup_task_id,
        communication_type="PROBATION_FOLLOWUP",
        communication_status=communication_status,
        **kwargs,
    )
    db.add(comm)
    db.flush()
    return comm


def make_text_version(
    db: Session,
    communication_id: int,
    text_content: str = "HR 与员工进行了沟通，员工反馈工作进展顺利。",
    version_no: int = 1,
) -> CommunicationTextVersion:
    import hashlib
    text_hash = hashlib.sha256(text_content.encode()).hexdigest()
    ver = CommunicationTextVersion(
        communication_id=communication_id,
        version_no=version_no,
        text_content=text_content,
        text_hash=text_hash,
        text_length=len(text_content),
    )
    db.add(ver)
    db.flush()

    # 更新沟通记录的当前版本引用
    comm = db.query(CommunicationRecord).filter(CommunicationRecord.id == communication_id).first()
    if comm:
        comm.current_text_version_id = ver.id
        comm.current_text_version_no = version_no
        comm.current_text_hash = text_hash
    db.flush()
    return ver


def create_probation_review(
    db: Session,
    employment_id: int,
    review_stage: str = "FOLLOWUP",
    review_status: str = "COMPLETED",
    **kwargs: Any,
) -> ProbationReview:
    review = ProbationReview(
        employment_id=employment_id,
        review_seq=1,
        review_stage=review_stage,
        review_status=review_status,
        **kwargs,
    )
    db.add(review)
    db.flush()
    return review


def create_separation(
    db: Session,
    employment_id: int,
    separation_type: str = "主动离职",
    **kwargs: Any,
) -> SeparationRecord:
    sep = SeparationRecord(
        employment_id=employment_id,
        separation_type=separation_type,
        **kwargs,
    )
    db.add(sep)
    db.flush()
    return sep


def create_regularization(
    db: Session,
    employment_id: int,
    decision: str = "APPROVED",
    is_effective: bool = True,
    **kwargs: Any,
) -> RegularizationRecord:
    reg = RegularizationRecord(
        employment_id=employment_id,
        decision=decision,
        is_effective=is_effective,
        **kwargs,
    )
    db.add(reg)
    db.flush()
    return reg
