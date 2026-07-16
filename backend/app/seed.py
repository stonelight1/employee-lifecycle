"""
数据库种子脚本 —— 创建默认跟进节点和测试数据。

用法: uv run python -m app.seed
"""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.followup_node import FollowupNodeDefinition
from app.models.employee import Employee
from app.models.employment import EmploymentRecord
from app.models.followup_task import FollowupTask
from app.enums import (
    ConfirmationMode,
    EmploymentStatus,
    EmployeeStatus,
    FollowupTaskStatus,
    ProbationStatus,
    TaskSource,
    TriggerType,
)


def create_default_nodes(db) -> list[FollowupNodeDefinition]:
    """幂等创建默认跟进节点。"""
    defaults = [
        {
            "node_code": "D7",
            "node_name": "入职后 7 天",
            "trigger_type": TriggerType.DAYS_AFTER_HIRE,
            "offset_days": 7,
            "confirmation_mode": ConfirmationMode.ALL,
            "enabled": True,
            "node_version": 1,
        },
        {
            "node_code": "D15",
            "node_name": "入职后 15 天",
            "trigger_type": TriggerType.DAYS_AFTER_HIRE,
            "offset_days": 15,
            "confirmation_mode": ConfirmationMode.ALL,
            "enabled": True,
            "node_version": 1,
        },
        {
            "node_code": "D30",
            "node_name": "入职后 30 天",
            "trigger_type": TriggerType.DAYS_AFTER_HIRE,
            "offset_days": 30,
            "confirmation_mode": ConfirmationMode.ALL,
            "enabled": True,
            "node_version": 1,
        },
        {
            "node_code": "D45",
            "node_name": "入职后 45 天",
            "trigger_type": TriggerType.DAYS_AFTER_HIRE,
            "offset_days": 45,
            "confirmation_mode": ConfirmationMode.ALL,
            "enabled": True,
            "node_version": 1,
        },
        {
            "node_code": "REG_INTERVIEW",
            "node_name": "转正面谈",
            "trigger_type": TriggerType.REGULARIZATION_INTERVIEW,
            "offset_days": None,
            "confirmation_mode": ConfirmationMode.ALL,
            "enabled": True,
            "node_version": 1,
        },
    ]

    created = []
    for data in defaults:
        existing = (
            db.query(FollowupNodeDefinition)
            .filter(FollowupNodeDefinition.node_code == data["node_code"])
            .first()
        )
        if not existing:
            node = FollowupNodeDefinition(**data)
            db.add(node)
            created.append(node)

    db.commit()
    for node in created:
        db.refresh(node)
    return created


def seed() -> None:
    """执行种子数据。"""
    db = SessionLocal()
    try:
        nodes = create_default_nodes(db)
        print(f"默认节点: 已创建 {len(nodes)} 个, 已存在 {5 - len(nodes)} 个")

        # 创建测试员工
        existing = db.query(Employee).filter(Employee.name == "测试员工").first()
        if not existing:
            emp = Employee(
                name="测试员工",
                normalized_name="测试员工",
                employee_no="EMP001",
                employee_status=EmployeeStatus.ACTIVE,
                source="seed",
            )
            db.add(emp)
            db.flush()

            # 创建任职
            employment = EmploymentRecord(
                employee_id=emp.id,
                employment_seq=1,
                employment_status=EmploymentStatus.ACTIVE,
                hire_date=date.today(),
                probation_status=ProbationStatus.IN_PROGRESS,
                department="技术部",
                position="工程师",
            )
            db.add(employment)
            db.flush()

            # 为每个启用节点生成自动任务
            enabled_nodes = (
                db.query(FollowupNodeDefinition)
                .filter(FollowupNodeDefinition.enabled == True)
                .all()
            )
            for node in enabled_nodes:
                if node.offset_days is not None:
                    planned = date(2026, 7, 1) + __import__("datetime").timedelta(
                        days=node.offset_days
                    )
                else:
                    planned = date(2026, 10, 1)  # 转正面谈默认日期

                import hashlib

                id_key = hashlib.sha256(
                    f"auto_task_{employment.id}_{node.id}".encode()
                ).hexdigest()

                task = FollowupTask(
                    employment_id=employment.id,
                    node_definition_id=node.id,
                    node_version=node.node_version,
                    node_code_snapshot=node.node_code,
                    task_name=node.node_name,
                    task_source=TaskSource.AUTO,
                    trigger_type_snapshot=node.trigger_type if isinstance(node.trigger_type, str) else node.trigger_type.value,
                    offset_days_snapshot=node.offset_days,
                    planned_date=planned,
                    original_planned_date=planned,
                    followup_status=FollowupTaskStatus.PENDING,
                    confirmation_mode=node.confirmation_mode,
                    idempotency_key=id_key,
                )
                db.add(task)

            db.commit()
            print(
                f"测试数据: 已创建员工 '{emp.name}' + 1 条任职 + {len(enabled_nodes)} 个任务"
            )
        else:
            print("测试数据: 已存在，跳过")

        print("种子数据完成！")
    except Exception as e:
        db.rollback()
        print(f"种子数据失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
