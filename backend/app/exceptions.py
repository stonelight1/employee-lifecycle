from __future__ import annotations


class AppException(Exception):
    """应用业务异常基类。"""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AppException):
    def __init__(self, message: str = "参数错误", details: dict | None = None):
        super().__init__("VALIDATION_ERROR", message, details)


class ResourceNotFound(AppException):
    def __init__(self, message: str = "资源不存在或不可见"):
        super().__init__("RESOURCE_NOT_FOUND", message)


class ResourceDeleted(AppException):
    def __init__(self, message: str = "资源已逻辑删除"):
        super().__init__("RESOURCE_DELETED", message)


class Conflict(AppException):
    def __init__(self, message: str = "状态或数据冲突"):
        super().__init__("CONFLICT", message)


class DuplicateRequest(AppException):
    def __init__(self, message: str = "重复请求"):
        super().__init__("DUPLICATE_REQUEST", message)


class VersionConflict(AppException):
    def __init__(self, message: str = "并发版本冲突"):
        super().__init__("VERSION_CONFLICT", message)


class InvalidStateTransition(AppException):
    def __init__(self, message: str = "非法状态流转"):
        super().__init__("INVALID_STATE_TRANSITION", message)


class EmployeeMatchAmbiguous(AppException):
    def __init__(self, message: str, candidates: list[dict] | None = None):
        super().__init__("EMPLOYEE_MATCH_AMBIGUOUS", message, {"candidates": candidates or []})


class ActiveEmploymentExists(AppException):
    def __init__(self, message: str = "员工已有有效任职记录"):
        super().__init__("ACTIVE_EMPLOYMENT_EXISTS", message)


class FinalProbationReviewRequired(AppException):
    def __init__(self):
        super().__init__(
            "FINAL_PROBATION_REVIEW_REQUIRED",
            "缺少已完成的最终试用期评估",
        )


class CommunicationTextRequired(AppException):
    def __init__(self):
        super().__init__("COMMUNICATION_TEXT_REQUIRED", "沟通文本为空")


class CommunicationTextTooLong(AppException):
    def __init__(self, max_length: int):
        super().__init__(
            "COMMUNICATION_TEXT_TOO_LONG",
            f"沟通文本过长，最大允许 {max_length} 字符",
        )


class AiNotConfigured(AppException):
    def __init__(self):
        super().__init__("AI_NOT_CONFIGURED", "AI 未配置或已关闭")


class AiSummaryProcessing(AppException):
    def __init__(self):
        super().__init__("AI_SUMMARY_PROCESSING", "AI 处理中")


class AiSummaryFailed(AppException):
    def __init__(self):
        super().__init__("AI_SUMMARY_FAILED", "AI 总结失败")


class AiResponseInvalid(AppException):
    def __init__(self, message: str = "AI 返回格式错误"):
        super().__init__("AI_RESPONSE_INVALID", message)


class AiSummaryOutdated(AppException):
    def __init__(self):
        super().__init__("AI_SUMMARY_OUTDATED", "沟通文本已修改，请重新生成 AI 建议")
