from __future__ import annotations

import enum
from typing import Optional


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class EmploymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SEPARATING = "SEPARATING"
    SEPARATED = "SEPARATED"


class ProbationStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_REVIEW = "PENDING_REVIEW"
    REGULARIZED = "REGULARIZED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


class FollowupTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CommunicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    VOIDED = "VOIDED"


class SummaryStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED = "CONFIRMED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"


class RiskLevel(str, enum.Enum):
    UNSPECIFIED = "UNSPECIFIED"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AssessmentSource(str, enum.Enum):
    AI = "AI"
    MANUAL = "MANUAL"


class ReviewStage(str, enum.Enum):
    FOLLOWUP = "FOLLOWUP"
    FINAL = "FINAL"


class RegularizationDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    EXTENDED = "EXTENDED"
    NOT_APPROVED = "NOT_APPROVED"


class ChangeType(str, enum.Enum):
    DEPARTMENT = "DEPARTMENT"
    POSITION = "POSITION"
    MANAGER = "MANAGER"


class ConfirmationMode(str, enum.Enum):
    ALL = "ALL"
    ANY = "ANY"


class ParticipantRole(str, enum.Enum):
    PARTICIPANT = "PARTICIPANT"
    CONFIRMER = "CONFIRMER"


class TriggerType(str, enum.Enum):
    DAYS_AFTER_HIRE = "DAYS_AFTER_HIRE"
    REGULARIZATION_INTERVIEW = "REGULARIZATION_INTERVIEW"
    MANUAL = "MANUAL"


class TodoStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ConfirmationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"


class OperationObjectType(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    EMPLOYMENT = "EMPLOYMENT"
    FOLLOWUP_NODE = "FOLLOWUP_NODE"
    FOLLOWUP_TASK = "FOLLOWUP_TASK"
    COMMUNICATION = "COMMUNICATION"
    AI_SUMMARY = "AI_SUMMARY"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    PROBATION_REVIEW = "PROBATION_REVIEW"
    REGULARIZATION = "REGULARIZATION"
    EMPLOYMENT_CHANGE = "EMPLOYMENT_CHANGE"
    SEPARATION = "SEPARATION"
    TODO = "TODO"


class TaskSource(str, enum.Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
