from __future__ import annotations

import enum
from typing import Optional


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ENTRY_ERROR = "ENTRY_ERROR"


class EmploymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SEPARATING = "SEPARATING"
    SEPARATED = "SEPARATED"
    CANCELLED = "CANCELLED"


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
    ROSTER_IMPORT = "ROSTER_IMPORT"
    ROSTER_ISSUE = "ROSTER_ISSUE"
    HR_CONFIRMATION = "HR_CONFIRMATION"
    EMPLOYEE_PROFILE = "EMPLOYEE_PROFILE"
    CONTRACT = "CONTRACT"
    FINANCIAL_ACCOUNT = "FINANCIAL_ACCOUNT"
    COMPENSATION = "COMPENSATION"
    ASSESSMENT = "ASSESSMENT"
    NOTE = "NOTE"
    ATTRIBUTE_HISTORY = "ATTRIBUTE_HISTORY"
    SEPARATION_CHECKLIST = "SEPARATION_CHECKLIST"
    ORGANIZATION_REFERENCE = "ORGANIZATION_REFERENCE"


class TaskSource(str, enum.Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class EmploymentType(str, enum.Enum):
    FORMAL = "FORMAL"
    INTERN = "INTERN"
    OUTSOURCED = "OUTSOURCED"
    COOPERATION = "COOPERATION"
    OTHER = "OTHER"


class WorkMode(str, enum.Enum):
    ONSITE = "ONSITE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    UNKNOWN = "UNKNOWN"


class ProfileCompleteness(str, enum.Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class AccountType(str, enum.Enum):
    BANK = "BANK"
    ALIPAY = "ALIPAY"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ContractType(str, enum.Enum):
    FIXED_TERM = "FIXED_TERM"
    INDEFINITE = "INDEFINITE"
    UNKNOWN = "UNKNOWN"


class SalaryType(str, enum.Enum):
    MONTHLY = "MONTHLY"
    DAILY = "DAILY"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class AssessmentType(str, enum.Enum):
    MBTI = "MBTI"
    PDP = "PDP"


class AttributeSource(str, enum.Enum):
    MANUAL = "MANUAL"
    ROSTER_IMPORT = "ROSTER_IMPORT"


class RosterImportMode(str, enum.Enum):
    INITIALIZE = "INITIALIZE"
    SYNC = "SYNC"


class RosterBatchStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    MAPPING_REQUIRED = "MAPPING_REQUIRED"
    PREVIEW_READY = "PREVIEW_READY"
    WAITING_RESOLUTION = "WAITING_RESOLUTION"
    READY = "READY"
    IMPORTING = "IMPORTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLBACK_PREVIEW = "ROLLBACK_PREVIEW"
    ROLLED_BACK = "ROLLED_BACK"


class RosterRowStatus(str, enum.Enum):
    NEW = "NEW"
    UPDATE = "UPDATE"
    UNCHANGED = "UNCHANGED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    IMPORTED = "IMPORTED"


class IssueSeverity(str, enum.Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"


class ResolutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"
    DEFERRED = "DEFERRED"


class ConfirmationItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    IGNORED = "IGNORED"


class OrgRefType(str, enum.Enum):
    DEPARTMENT = "DEPARTMENT"
    POSITION = "POSITION"
    TEAM = "TEAM"


class ChecklistItemType(str, enum.Enum):
    SALARY = "SALARY"
    SOCIAL_INSURANCE = "SOCIAL_INSURANCE"
    HOUSING_FUND = "HOUSING_FUND"
    DEVICE = "DEVICE"
    ACCOUNT = "ACCOUNT"
