"""
从 SQLAlchemy 模型元数据自动生成 MySQL DDL 脚本。
用法：python scripts/generate_mysql_ddl.py

每次修改数据库模型后，运行此脚本更新 docs/schema-mysql.sql。
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加后端路径以便导入模型
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///data/employee_lifecycle.db")

from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.mysql import  TEXT as MySQLTEXT
from sqlalchemy.dialects.mysql.base import MySQLDDLCompiler
from app.models.base import Base
from app.models import *  # noqa: F401, F403


def table_order_key(table_name: str) -> tuple:
    """按逻辑分组排序表"""
    groups = {
        "alembic_version": (0, ""),
        "employee": (1, "01_employee"),
        "employee_profile": (1, "02_employee_profile"),
        "employment_record": (1, "03_employment_record"),
        "employment_change": (1, "04_employment_change"),
        "employment_contract": (1, "05_employment_contract"),
        "compensation_record": (1, "06_compensation_record"),
        "employee_financial_account": (1, "07_employee_financial_account"),
        "employee_assessment": (1, "08_employee_assessment"),
        "employee_note": (1, "09_employee_note"),
        "employee_attribute_history": (1, "10_employee_attribute_history"),
        "followup_node_definition": (2, "11_followup_node_definition"),
        "followup_task": (2, "12_followup_task"),
        "followup_task_participant": (2, "13_followup_task_participant"),
        "followup_task_confirmation": (2, "14_followup_task_confirmation"),
        "communication_record": (3, "15_communication_record"),
        "communication_text_version": (3, "16_communication_text_version"),
        "ai_summary_version": (3, "17_ai_summary_version"),
        "risk_assessment": (3, "18_risk_assessment"),
        "probation_review": (3, "19_probation_review"),
        "regularization_record": (3, "20_regularization_record"),
        "separation_record": (3, "21_separation_record"),
        "separation_checklist_item": (3, "22_separation_checklist_item"),
        "system_todo": (4, "23_system_todo"),
        "operation_log": (4, "24_operation_log"),
        "organization_reference": (4, "25_organization_reference"),
        "hr_confirmation_item": (5, "30_hr_confirmation_item"),
        "roster_import_batch": (6, "40_roster_import_batch"),
        "roster_import_row": (6, "41_roster_import_row"),
        "roster_import_issue": (6, "42_roster_import_issue"),
        "roster_import_operation": (6, "43_roster_import_operation"),
        "roster_column_alias": (6, "44_roster_column_alias"),
        "roster_value_alias": (6, "45_roster_value_alias"),
    }
    return groups.get(table_name, (99, table_name))


def get_column_type_string(col) -> str:
    """获取 MySQL 兼容的列类型字符串"""
    # 尝试用 MySQL 方言编译
    try:
        engine = create_engine("mysql+pymysql://", module=__import__("sqlalchemy.dialects.mysql"))
        compiled = col.type.compile(dialect=engine.dialect)
        if compiled:
            return compiled
    except Exception:
        pass

    # 手动映射常见类型
    type_map = {
        "INTEGER": "INT",
        "VARCHAR": "VARCHAR",
        "BOOLEAN": "TINYINT(1)",
        "DATETIME": "DATETIME",
        "DATE": "DATE",
        "NUMERIC": "DECIMAL",
        "TEXT": "TEXT",
        "FLOAT": "FLOAT",
    }
    base = col.type.__class__.__name__.upper()
    if base == "INTEGER":
        if col.primary_key:
            return "INT AUTO_INCREMENT"
        return "INT"
    if base == "BOOLEAN":
        return "TINYINT(1)"
    if base == "NUMERIC":
        if hasattr(col.type, "precision") and hasattr(col.type, "scale"):
            if col.type.precision and col.type.scale is not None:
                return f"DECIMAL({col.type.precision},{col.type.scale})"
        return "DECIMAL(12,2)"
    if base == "VARCHAR":
        length = getattr(col.type, "length", 255)
        return f"VARCHAR({length})" if length else "VARCHAR(255)"
    if base == "TEXT":
        return "TEXT"
    if base == "DATETIME":
        return "DATETIME"
    if base == "DATE":
        return "DATE"
    if base == "FLOAT":
        return "FLOAT"
    if base in ("INT", "SMALLINT", "BIGINT"):
        return base
    return str(col.type)


def generate_ddl() -> str:
    """生成完整的 MySQL DDL"""
    metadata: MetaData = Base.metadata
    tables = sorted(metadata.tables.values(), key=lambda t: table_order_key(t.name))

    lines = [
        "-- ================================================================",
        "-- employee-lifecycle 数据库 MySQL DDL",
        "-- 生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "-- 来源：SQLAlchemy 模型元数据自动生成",
        "-- 注意：每次修改模型后运行 scripts/generate_mysql_ddl.py 更新本文件",
        "-- ================================================================",
        "",
        "CREATE DATABASE IF NOT EXISTS employee_lifecycle",
        "    DEFAULT CHARACTER SET utf8mb4",
        "    DEFAULT COLLATE utf8mb4_unicode_ci;",
        "",
        "USE employee_lifecycle;",
        "",
    ]

    for table in tables:
        if table.name == "alembic_version":
            continue

        lines.append(f"-- ---------------------------------------------------")
        lines.append(f"-- 表：{table.name}")
        lines.append(f"-- ---------------------------------------------------")
        lines.append(f"CREATE TABLE `{table.name}` (")

        col_defs = []
        for col in table.columns:
            parts = [f"  `{col.name}`"]

            # 类型
            parts.append(get_column_type_string(col))

            # 是否非空
            if not col.nullable:
                parts.append("NOT NULL")
            else:
                parts.append("NULL")

            # 默认值
            if col.server_default is not None:
                default = col.server_default.arg
                if isinstance(default, str):
                    if default.upper() in ("CURRENT_TIMESTAMP", "NOW()"):
                        parts.append("DEFAULT CURRENT_TIMESTAMP")
                    else:
                        parts.append(f"DEFAULT '{default}'")
                else:
                    parts.append(f"DEFAULT {default}")
            elif col.default is not None and not callable(col.default):
                # Python 层默认值（仅当是简单值）
                if isinstance(col.default, (int, float, bool)):
                    parts.append(f"DEFAULT {int(col.default) if isinstance(col.default, bool) else col.default}")
                elif isinstance(col.default, str) and col.default not in ("None", ""):
                    parts.append(f"DEFAULT '{col.default}'")

            # 注释（从模型 comment 参数来）
            if col.comment:
                # 转义注释中的单引号
                safe_comment = col.comment.replace("'", "\\'")
                parts.append(f"COMMENT '{safe_comment}'")

            col_defs.append(" ".join(parts))

        # 主键
        pk_cols = [col.name for col in table.primary_key.columns]
        if pk_cols:
            col_defs.append(f"  PRIMARY KEY (`{'`, `'.join(pk_cols)}`)")

        # 唯一约束
        for constraint in table.constraints:
            if constraint.name and "pk_" not in str(constraint.name).lower():
                if isinstance(constraint, __import__("sqlalchemy").UniqueConstraint):
                    cols = [c.name for c in constraint.columns]
                    col_defs.append(f"  UNIQUE KEY `{constraint.name}` (`{'`, `'.join(cols)}`)")

        # 索引
        for index in table.indexes:
            if index.name and index.name != "PRIMARY":
                cols = []
                for c in index.columns:
                    cols.append(f"`{c.name}`")
                unique = "UNIQUE " if index.unique else ""
                col_defs.append(f"  {unique}KEY `{index.name}` ({', '.join(cols)})")

        lines.append(",\n".join(col_defs))
        lines.append(f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci")
        lines.append(f"  COMMENT='{_get_table_comment(table)}';")
        lines.append("")

    lines.append("-- ================================================================")
    lines.append("-- 外键约束")
    lines.append("-- ================================================================")
    for table in tables:
        if table.name == "alembic_version":
            continue
        for fk in table.foreign_keys:
            parent_col = fk.column
            lines.append(
                f"ALTER TABLE `{table.name}` ADD CONSTRAINT `fk_{table.name}_{fk.parent.name}`"
            )
            lines.append(
                f"  FOREIGN KEY (`{fk.parent.name}`) REFERENCES `{parent_col.table.name}` (`{parent_col.name}`)"
            )
            lines.append(f"  ON DELETE RESTRICT ON UPDATE CASCADE;")
            lines.append("")

    lines.append("-- ================================================================")
    lines.append("-- 索引补充（非外键索引已在 CREATE TABLE 中包含）")
    lines.append("-- ================================================================")
    lines.append("")

    return "\n".join(lines)


def _get_table_comment(table) -> str:
    """获取表的中文注释"""
    # 从 model mapping 获取
    model_comments = {
        "employee": "员工主表",
        "employee_profile": "员工档案/个人信息表",
        "employment_record": "任职记录表",
        "employment_change": "任职异动记录表",
        "employment_contract": "劳动合同信息表",
        "compensation_record": "薪酬记录表",
        "employee_financial_account": "员工财务账户（银行卡/支付宝等）",
        "employee_assessment": "员工考核/评估记录表",
        "employee_note": "员工备注表",
        "employee_attribute_history": "员工属性变更历史表",
        "followup_node_definition": "跟进节点定义表",
        "followup_task": "跟进任务表",
        "followup_task_participant": "跟进任务参与人表",
        "followup_task_confirmation": "跟进任务确认记录表",
        "communication_record": "沟通记录表",
        "communication_text_version": "沟通文本版本历史表",
        "ai_summary_version": "AI摘要版本表",
        "risk_assessment": "风险评估记录表",
        "probation_review": "试用期评审记录表",
        "regularization_record": "转正审批记录表",
        "separation_record": "离职记录表",
        "separation_checklist_item": "离职清单项表",
        "system_todo": "系统待办事项表",
        "operation_log": "操作审计日志表",
        "organization_reference": "组织架构参考数据表（部门/职位字典）",
        "hr_confirmation_item": "HR确认事项表（花名册导入需人工确认项）",
        "roster_import_batch": "花名册导入批次表",
        "roster_import_row": "花名册导入行数据表",
        "roster_import_issue": "花名册导入问题表",
        "roster_import_operation": "花名册导入操作记录表",
        "roster_column_alias": "花名册表头别名映射表",
        "roster_value_alias": "花名册值别名映射表",
    }
    return model_comments.get(table.name, "")


if __name__ == "__main__":
    ddl = generate_ddl()
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    output_path = docs_dir / "schema-mysql.sql"
    output_path.write_text(ddl, encoding="utf-8")
    print(f"DDL generated: {output_path}")
    print(f"Total length: {len(ddl)} characters")
