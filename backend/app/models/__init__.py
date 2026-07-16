"""
数据模型 —— 集中导出所有模型以便 Alembic 自动发现。
各模型文件从 .base 导入 Base 和 CommonMixin。
"""

from .base import CommonMixin

from .employee import Employee
from .employment import EmploymentRecord
from .followup_node import FollowupNodeDefinition
from .followup_task import FollowupTask
from .followup_participant import FollowupTaskParticipant, FollowupTaskConfirmation
from .communication import CommunicationRecord
from .text_version import CommunicationTextVersion
from .ai_summary import AiSummaryVersion
from .risk import RiskAssessment
from .probation import ProbationReview
from .regularization import RegularizationRecord
from .change import EmploymentChange
from .separation import SeparationRecord
from .todo import SystemTodo
from .operation_log import OperationLog

__all__ = [
    "CommonMixin",
    "Employee",
    "EmploymentRecord",
    "FollowupNodeDefinition",
    "FollowupTask",
    "FollowupTaskParticipant",
    "FollowupTaskConfirmation",
    "CommunicationRecord",
    "CommunicationTextVersion",
    "AiSummaryVersion",
    "RiskAssessment",
    "ProbationReview",
    "RegularizationRecord",
    "EmploymentChange",
    "SeparationRecord",
    "SystemTodo",
    "OperationLog",
]
