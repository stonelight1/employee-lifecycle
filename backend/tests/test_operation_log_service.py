"""
操作日志测试 —— 验证 list_logs 函数基本功能
"""

from __future__ import annotations

from app.services.operation_log_service import list_logs


class TestOperationLog:
    """验证 list_logs 的查询和分页功能"""

    def test_list_empty(self, db_session, default_user):
        logs, total = list_logs(db_session, page=1, page_size=10)
        assert total == 0
        assert logs == []

    def test_list_pagination_params(self, db_session, default_user):
        """默认 page=1, page_size=20"""
        logs, total = list_logs(db_session)
        assert total == 0
        assert logs == []
        # 带分页参数也不报错
        logs2, total2 = list_logs(db_session, page=2, page_size=5)
        assert total2 == 0

    def test_list_with_filters(self, db_session, default_user):
        """带过滤参数不报错"""
        logs, total = list_logs(db_session, object_type="EMPLOYEE", object_id="999")
        assert total == 0
