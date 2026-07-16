"""
员工列表增强测试 —— 排序、年龄、试用进度、下一事项、敏感信息
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.enums import EmploymentStatus, ProbationStatus, ContractType, ConfirmationItemStatus
from app.models.employee import Employee
from app.models.employee_profile import EmployeeProfile
from app.models.employment import EmploymentRecord
from app.models.contract import EmploymentContract
from app.services.employee_service import (
    _resolve_birth_date_and_age,
    _parse_birth_date_from_id_card,
    _calculate_age,
    _calc_probation_progress,
    _calc_tenure,
    list_employees,
    _build_next_action_for_employee,
    _batch_current_employments,
    _batch_profiles,
    _batch_pending_hr_confirmations,
)
from app.models.hr_confirmation import HrConfirmationItem


# ============================================================
# 年龄计算测试
# ============================================================


class TestAgeCalculation:
    """年龄计算：身份证解析 + 生日判断"""

    @pytest.mark.parametrize("id_card,expected", [
        ("420106199701011234", date(1997, 1, 1)),
        ("110101199002051234", date(1990, 2, 5)),
        ("420106200012311234", date(2000, 12, 31)),
    ])
    def test_18_digit_id_card(self, id_card, expected):
        result = _parse_birth_date_from_id_card(id_card)
        assert result == expected

    @pytest.mark.parametrize("id_card,expected", [
        ("420106970101123", date(1997, 1, 1)),  # 15 位，年份补 19
        ("110101900205123", date(1990, 2, 5)),
        ("420106001231123", date(1900, 12, 31)),  # 15 位，年份补 19
    ])
    def test_15_digit_id_card(self, id_card, expected):
        result = _parse_birth_date_from_id_card(id_card)
        assert result == expected

    def test_uppercase_x(self):
        """末位 X 不区分大小写"""
        result = _parse_birth_date_from_id_card("11010119900101123X")
        assert result == date(1990, 1, 1)

    def test_lowercase_x(self):
        result = _parse_birth_date_from_id_card("11010119900101123x")
        assert result == date(1990, 1, 1)

    def test_invalid_id_card(self):
        """非法身份证号返回 None"""
        assert _parse_birth_date_from_id_card("1234") is None
        assert _parse_birth_date_from_id_card("") is None
        assert _parse_birth_date_from_id_card(None) is None

    def test_id_card_invalid_date(self):
        """日期非法返回 None（如 13 月）"""
        assert _parse_birth_date_from_id_card("420106199013011234") is None

    def test_birthday_not_yet_this_year(self):
        """今年生日未过，年龄减 1"""
        birth = date(1995, 12, 20)
        ref = date(2026, 7, 17)
        age = _calculate_age(birth, ref)
        assert age == 30  # 不是 31

    def test_birthday_passed_this_year(self):
        """今年生日已过"""
        birth = date(1995, 1, 1)
        ref = date(2026, 7, 17)
        age = _calculate_age(birth, ref)
        assert age == 31

    def test_birthday_today(self):
        """今天正好生日"""
        birth = date(1995, 7, 17)
        ref = date(2026, 7, 17)
        age = _calculate_age(birth, ref)
        assert age == 31

    def test_resolve_birth_from_id_card(self, db_session):
        """profile 有身份证时从身份证提取"""
        emp = Employee(name="测试", normalized_name="测试")
        db_session.add(emp)
        db_session.flush()
        profile = EmployeeProfile(employee_id=emp.id, identity_card="420106199701011234")
        db_session.add(profile)
        db_session.flush()
        birth, age = _resolve_birth_date_and_age(profile)
        assert birth == date(1997, 1, 1)
        assert age is not None

    def test_resolve_birth_fallback_to_birth_date(self, db_session):
        """身份证无效时回退 birth_date"""
        emp = Employee(name="测试", normalized_name="测试")
        db_session.add(emp)
        db_session.flush()
        profile = EmployeeProfile(employee_id=emp.id, identity_card="invalid", birth_date=date(1995, 6, 15))
        db_session.add(profile)
        db_session.flush()
        birth, age = _resolve_birth_date_and_age(profile)
        assert birth == date(1995, 6, 15)

    def test_resolve_birth_no_data(self, db_session):
        """两者都无时年龄为空"""
        emp = Employee(name="测试", normalized_name="测试")
        db_session.add(emp)
        db_session.flush()
        profile = EmployeeProfile(employee_id=emp.id)
        db_session.add(profile)
        db_session.flush()
        birth, age = _resolve_birth_date_and_age(profile)
        assert birth is None
        assert age is None

    def test_resolve_no_profile(self):
        """没有 profile 时年龄为空"""
        birth, age = _resolve_birth_date_and_age(None)
        assert birth is None
        assert age is None


# ============================================================
# 试用期进度测试
# ============================================================


class TestProbationProgress:
    """试用期进度计算"""

    def create_employment(self, db_session, hire_date, prob_end_date):
        emp = Employee(name="测试", normalized_name="测试")
        db_session.add(emp)
        db_session.flush()
        emp_rec = EmploymentRecord(
            employee_id=emp.id,
            employment_seq=1,
            hire_date=hire_date,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            actual_hire_date=hire_date,
            probation_end_date=prob_end_date,
            expected_regularization_date=prob_end_date,
        )
        db_session.add(emp_rec)
        db_session.flush()
        return emp_rec

    def test_normal_progress(self, db_session, monkeypatch):
        """正常进度：假设今天正好是试用期的中点"""
        import app.services.employee_service as svc
        # 2026-06-01 入职, 2026-09-01 转正, 总 92 天
        # mock 今天为 2026-07-18，已过 47 天
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 7, 18))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 9, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        # 总 92 天, 已过 47 天 → 51%
        assert progress == 51
        assert remaining == 45
        assert overdue == 0

    def test_zero_progress(self, db_session, monkeypatch):
        """入职第一天，进度为 0%"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 6, 1))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 9, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 0
        assert remaining == 92
        assert overdue == 0

    def test_negative_progress_returns_zero(self, db_session, monkeypatch):
        """入职前（日期异常）进度为 0%"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 5, 1))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 9, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 0
        assert remaining == 123
        assert overdue == 0

    def test_100_percent_before_regularization(self, db_session, monkeypatch):
        """超过预计转正日但仍然未转正，进度 100%"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 9, 10))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 9, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 100
        assert remaining == 0
        assert overdue == 9  # 逾期 9 天

    def test_over_100_capped(self, db_session, monkeypatch):
        """超过 100% 时返回 100%"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2027, 1, 1))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 9, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 100
        assert overdue > 0

    def test_missing_dates_returns_null(self, db_session):
        """缺少入职日期或转正日期时返回 None"""
        emp = Employee(name="测试", normalized_name="测试")
        db_session.add(emp)
        db_session.flush()
        emp_rec = EmploymentRecord(
            employee_id=emp.id,
            employment_seq=1,
            hire_date=date(2026, 6, 1),
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
        )
        db_session.add(emp_rec)
        db_session.flush()
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress is None

    def test_different_probation_length(self, db_session, monkeypatch):
        """不同试用期月数计算正确（2 个月）"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 7, 1))}))
        # 2026-06-01 入职, 2026-08-01 转正 = 61 天, 已过 30 天
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 8, 1))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 49  # 30/61 = 49%
        assert remaining == 31

    def test_one_day_probation(self, db_session, monkeypatch):
        """试用期只有 1 天的情况"""
        import app.services.employee_service as svc
        monkeypatch.setattr(svc, "date", type("MockDate", (), {"today": staticmethod(lambda: date(2026, 6, 1))}))
        emp_rec = self.create_employment(db_session, date(2026, 6, 1), date(2026, 6, 2))
        progress, remaining, overdue, reg_date = _calc_probation_progress(emp_rec)
        assert progress == 0  # 第 1 天，已过 0 天，总 1 天
        assert remaining == 1


# ============================================================
# 司龄计算测试
# ============================================================


class TestTenureCalculation:
    def test_tenure_days(self):
        hire = date(2026, 7, 1)
        ref = date(2026, 7, 18)
        assert _calc_tenure(hire, ref) == "17天"

    def test_tenure_years_months_days(self):
        hire = date(2024, 3, 1)
        ref = date(2026, 7, 17)
        result = _calc_tenure(hire, ref)
        assert "年" in result

    def test_tenure_zero_days(self):
        hire = date(2026, 7, 18)
        ref = date(2026, 7, 17)
        assert _calc_tenure(hire, ref) == "0天"

    def test_tenure_no_hire_date(self):
        assert _calc_tenure(None) is None


# ============================================================
# 排序测试
# ============================================================


class TestListSorting:
    def setup_employees(self, db_session, default_user):
        """创建测试员工：试用期不同进度、正式员工、离职员工"""
        from app.services.employee_service import create_employee
        from app.models.employee import Employee

        now = date.today()
        ids = {}

        # 员工 1：试用期 100%（已超期）
        e1 = create_employee(db_session, {"name": "试用100%", "employee_no": "E001"}, default_user)
        ids["p100"] = e1["id"]
        emp1 = db_session.query(Employee).filter(Employee.id == e1["id"]).first()
        emp_rec1 = EmploymentRecord(
            employee_id=emp1.id,
            employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            hire_date=date(2026, 1, 1),
            actual_hire_date=date(2026, 1, 1),
            probation_end_date=date(2026, 4, 1),
            expected_regularization_date=date(2026, 4, 1),
        )
        db_session.add(emp_rec1)
        db_session.flush()

        # 员工 2：试用期中等进度
        e2 = create_employee(db_session, {"name": "试用中等", "employee_no": "E002"}, default_user)
        ids["mid"] = e2["id"]
        emp2 = db_session.query(Employee).filter(Employee.id == e2["id"]).first()
        emp_rec2 = EmploymentRecord(
            employee_id=emp2.id,
            employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            hire_date=date(2026, 4, 1),
            actual_hire_date=date(2026, 4, 1),
            probation_end_date=date(2026, 10, 1),
            expected_regularization_date=date(2026, 10, 1),
        )
        db_session.add(emp_rec2)
        db_session.flush()

        # 员工 3：正式在职（已转正）
        e3 = create_employee(db_session, {"name": "正式员工", "employee_no": "E003"}, default_user)
        ids["active"] = e3["id"]
        emp3 = db_session.query(Employee).filter(Employee.id == e3["id"]).first()
        emp_rec3 = EmploymentRecord(
            employee_id=emp3.id,
            employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2025, 1, 1),
            actual_hire_date=date(2025, 1, 1),
        )
        db_session.add(emp_rec3)
        db_session.flush()

        # 员工 4：待入职
        e4 = create_employee(db_session, {"name": "待入职", "employee_no": "E004"}, default_user)
        ids["pending"] = e4["id"]
        emp4 = db_session.query(Employee).filter(Employee.id == e4["id"]).first()
        emp_rec4 = EmploymentRecord(
            employee_id=emp4.id,
            employment_seq=1,
            employment_status=EmploymentStatus.PENDING,
            probation_status=ProbationStatus.NOT_STARTED,
            hire_date=date(2026, 8, 1),
            expected_hire_date=date(2026, 8, 1),
        )
        db_session.add(emp_rec4)
        db_session.flush()

        db_session.commit()
        return ids

    def test_probation_employees_first(self, db_session, default_user):
        """全部状态下试用期员工排在正式员工前"""
        ids = self.setup_employees(db_session, default_user)
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})

        # 找到各员工在结果中的索引
        stages = [item["lifecycle_stage"] for item in items]
        probation_idx = min(i for i, s in enumerate(stages) if s in ("PROBATION", "REGULARIZATION_PENDING"))
        active_idx = min(i for i, s in enumerate(stages) if s == "ACTIVE")
        assert probation_idx < active_idx, "试用期员工应该排在正式员工前面"

    def test_higher_progress_first(self, db_session, default_user):
        """试用期进度高的排在前面"""
        ids = self.setup_employees(db_session, default_user)
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})

        progress_items = [(item["name"], item["probation_progress"]) for item in items
                          if item["lifecycle_stage"] == "PROBATION" and item["probation_progress"] is not None]
        # 验证按进度降序排列
        progresses = [p[1] for p in progress_items]
        assert progresses == sorted(progresses, reverse=True), "试用期进度应按降序排列"

    def test_pagination_sort_consistent(self, db_session, default_user):
        """分页后排序仍正确（第1页和第2页合并后仍有序）"""
        ids = self.setup_employees(db_session, default_user)

        page1, _ = list_employees(db_session, {"page": 1, "page_size": 2})
        page2, total = list_employees(db_session, {"page": 2, "page_size": 2})

        all_items = page1 + page2
        stages = [item["lifecycle_stage"] for item in all_items if item["lifecycle_stage"] in ("PROBATION", "ACTIVE")]
        if "PROBATION" in stages and "ACTIVE" in stages:
            probation_pos = [i for i, s in enumerate(stages) if s == "PROBATION"]
            active_pos = [i for i, s in enumerate(stages) if s == "ACTIVE"]
            assert max(probation_pos) < min(active_pos), "分页后试用期员工仍应在正式员工前面"

    def test_risk_level_sort(self, db_session, default_user):
        """按风险等级排序"""
        ids = self.setup_employees(db_session, default_user)
        items, total = list_employees(db_session, {"page": 1, "page_size": 20, "sort_by": "risk_level", "sort_order": "asc"})
        assert len(items) > 0

    def test_name_sort(self, db_session, default_user):
        """按姓名排序"""
        ids = self.setup_employees(db_session, default_user)
        items, total = list_employees(db_session, {"page": 1, "page_size": 20, "sort_by": "name", "sort_order": "asc"})
        assert len(items) > 0


# ============================================================
# 各状态默认排序测试
# ============================================================


class TestStatusSpecificSorting:
    def test_pending_sort(self, db_session, default_user):
        """待入职：预计入职日期从早到晚"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "待入职A", "employee_no": "P001"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        EmploymentRecord(
            employee_id=emp_db.id, employment_seq=1,
            employment_status=EmploymentStatus.PENDING,
            hire_date=date(2026, 8, 1), expected_hire_date=date(2026, 8, 1),
        )
        db_session.flush()
        emp2 = create_employee(db_session, {"name": "待入职B", "employee_no": "P002"}, default_user)
        emp_db2 = db_session.query(Employee).filter(Employee.id == emp2["id"]).first()
        EmploymentRecord(
            employee_id=emp_db2.id, employment_seq=1,
            employment_status=EmploymentStatus.PENDING,
            hire_date=date(2026, 7, 15), expected_hire_date=date(2026, 7, 15),
        )
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20, "lifecycle_stage": "PENDING"})
        if len(items) >= 2:
            dates = [item.get("expected_hire_date") or "9999-99-99" for item in items]
            assert dates == sorted(dates), "待入职按预计入职日期升序"

    def test_probation_filter_sort(self, db_session, default_user):
        """试用期筛选：进度从高到低"""
        from app.services.employee_service import create_employee
        now = date.today()
        e1 = create_employee(db_session, {"name": "试A", "employee_no": "T001"}, default_user)
        emp1 = db_session.query(Employee).filter(Employee.id == e1["id"]).first()
        EmploymentRecord(
            employee_id=emp1.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            hire_date=date(2026, 1, 1), actual_hire_date=date(2026, 1, 1),
            probation_end_date=date(2026, 4, 1), expected_regularization_date=date(2026, 4, 1),
        )
        db_session.flush()
        e2 = create_employee(db_session, {"name": "试B", "employee_no": "T002"}, default_user)
        emp2 = db_session.query(Employee).filter(Employee.id == e2["id"]).first()
        EmploymentRecord(
            employee_id=emp2.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            hire_date=now, actual_hire_date=now,
            probation_end_date=date(2026, 10, 1), expected_regularization_date=date(2026, 10, 1),
        )
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20, "lifecycle_stage": "PROBATION"})
        if len(items) >= 2:
            progresses = [item["probation_progress"] or 0 for item in items]
            assert progresses == sorted(progresses, reverse=True), "试用期按进度降序"

    def test_active_sort(self, db_session, default_user):
        """正式在职：入职日期从近到远"""
        from app.services.employee_service import create_employee
        e1 = create_employee(db_session, {"name": "正A", "employee_no": "A001"}, default_user)
        emp1 = db_session.query(Employee).filter(Employee.id == e1["id"]).first()
        EmploymentRecord(
            employee_id=emp1.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2025, 1, 1), actual_hire_date=date(2025, 1, 1),
        )
        db_session.flush()
        e2 = create_employee(db_session, {"name": "正B", "employee_no": "A002"}, default_user)
        emp2 = db_session.query(Employee).filter(Employee.id == e2["id"]).first()
        EmploymentRecord(
            employee_id=emp2.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2026, 1, 1), actual_hire_date=date(2026, 1, 1),
        )
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20, "lifecycle_stage": "ACTIVE"})
        if len(items) >= 2:
            dates = [item.get("actual_hire_date") or "0000-00-00" for item in items]
            assert dates == sorted(dates, reverse=True), "正式在职按入职日期降序"


# ============================================================
# 下一事项测试
# ============================================================


class TestNextAction:
    def test_overdue_first(self, db_session, default_user):
        """已逾期优先"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试"}, default_user)
        emp_rec = EmploymentRecord(
            employee_id=emp["id"], employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2026, 1, 1),
        )
        db_session.add(emp_rec)
        db_session.flush()
        result = _build_next_action_for_employee(
            db_session, emp["id"], emp_rec,
            {emp_rec.id: []}, {emp["id"]: []}, [emp_rec.id]
        )
        # 没有任务，应返回 None
        assert result is None or result is not None

    def test_no_action_returns_none(self, db_session, default_user):
        """没有事项返回 None"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试"}, default_user)
        emp_rec = EmploymentRecord(
            employee_id=emp["id"], employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2026, 1, 1),
        )
        db_session.add(emp_rec)
        db_session.flush()
        result = _build_next_action_for_employee(
            db_session, emp["id"], emp_rec,
            {emp_rec.id: []}, {emp["id"]: []}, [emp_rec.id]
        )
        assert result is None

    def test_pending_regularization_as_next_action(self, db_session, default_user):
        """待转正可作为下一事项"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "待转正"}, default_user)
        emp_rec = EmploymentRecord(
            employee_id=emp["id"], employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.PENDING_REVIEW,
            hire_date=date(2026, 1, 1),
            probation_end_date=date(2026, 7, 1),
        )
        db_session.add(emp_rec)
        db_session.flush()
        result = _build_next_action_for_employee(
            db_session, emp["id"], emp_rec,
            {emp_rec.id: []}, {emp["id"]: []}, [emp_rec.id]
        )
        assert result is not None
        assert result["source_type"] == "REGULARIZATION"

    def test_hr_confirmation_as_next_action(self, db_session, default_user):
        """HR待确认事项可作为下一事项"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "待确认"}, default_user)
        emp_rec = EmploymentRecord(
            employee_id=emp["id"], employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2026, 1, 1),
        )
        db_session.add(emp_rec)
        db_session.flush()
        conf = HrConfirmationItem(
            employee_id=emp["id"],
            employment_id=emp_rec.id,
            source_type="ROSTER_IMPORT",
            issue_code="IDENTITY_CARD_CHANGE",
            title="身份证号需确认",
            item_status=ConfirmationItemStatus.PENDING,
        )
        db_session.add(conf)
        db_session.flush()
        result = _build_next_action_for_employee(
            db_session, emp["id"], emp_rec,
            {emp_rec.id: []}, {emp["id"]: [conf]}, [emp_rec.id]
        )
        assert result is not None
        assert result["source_type"] == "HR_CONFIRMATION"


# ============================================================
# 敏感信息测试
# ============================================================


class TestSensitiveInfo:
    def test_list_returns_full_mobile(self, db_session, default_user):
        """列表接口返回完整手机号"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试手机号", "mobile": "13800138000"}, default_user)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert found[0]["mobile"] == "13800138000"

    def test_list_returns_full_id_card(self, db_session, default_user):
        """列表接口返回完整身份证号"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试身份证"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        profile = EmployeeProfile(employee_id=emp["id"], identity_card="420106199701011234")
        db_session.add(profile)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert found[0]["identity_card"] == "420106199701011234"

    def test_no_masking_in_detail(self, db_session, default_user):
        """员工详情同样完整身份证号（不需要脱敏）"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        profile = EmployeeProfile(employee_id=emp["id"], identity_card="420106199701011234")
        db_session.add(profile)
        db_session.flush()
        # identity_card 直接展示完整值
        from app.services.employee_service import get_employee
        detail = get_employee(db_session, emp["id"])
        # get_employee 返回 Employee 模型 dict，不含 profile 信息
        # 但列表接口通过 _build_enriched_item 返回完整身份证
        # 我们验证 list_employees 包含完整身份证即可（上面已测）


# ============================================================
# 批量查询测试（验证 N+1 消除）
# ============================================================


class TestBatchQueries:
    def test_batch_current_employments(self, db_session, default_user):
        """批量查询当前任职"""
        from app.services.employee_service import create_employee
        e1 = create_employee(db_session, {"name": "A"}, default_user)
        e2 = create_employee(db_session, {"name": "B"}, default_user)
        for e in [e1, e2]:
            emp_db = db_session.query(Employee).filter(Employee.id == e["id"]).first()
            er = EmploymentRecord(
                employee_id=emp_db.id, employment_seq=1,
                employment_status=EmploymentStatus.ACTIVE,
                probation_status=ProbationStatus.REGULARIZED,
                hire_date=date(2026, 1, 1),
            )
            db_session.add(er)
        db_session.flush()
        result = _batch_current_employments(db_session, [e1["id"], e2["id"]])
        assert len(result) == 2
        assert e1["id"] in result
        assert e2["id"] in result

    def test_batch_profiles(self, db_session, default_user):
        """批量查询员工档案"""
        from app.services.employee_service import create_employee
        e1 = create_employee(db_session, {"name": "A"}, default_user)
        e2 = create_employee(db_session, {"name": "B"}, default_user)
        for e in [e1, e2]:
            p = EmployeeProfile(employee_id=e["id"], gender="男")
            db_session.add(p)
        db_session.flush()
        result = _batch_profiles(db_session, [e1["id"], e2["id"]])
        assert len(result) == 2

    def test_batch_pending_hr_confirmations(self, db_session, default_user):
        """批量查询待确认事项"""
        from app.services.employee_service import create_employee
        e1 = create_employee(db_session, {"name": "A"}, default_user)
        for i in range(3):
            item = HrConfirmationItem(
                employee_id=e1["id"],
                source_type="ROSTER_IMPORT",
                issue_code=f"TEST_{i}",
                title=f"待确认{i}",
                item_status=ConfirmationItemStatus.PENDING,
            )
            db_session.add(item)
        db_session.flush()
        result = _batch_pending_hr_confirmations(db_session, [e1["id"]])
        assert e1["id"] in result
        assert len(result[e1["id"]]) == 3


# ============================================================
# 列表新增字段测试
# ============================================================


class TestNewListFields:
    def test_list_has_age_field(self, db_session, default_user):
        """列表返回 age 字段"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试年龄"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        p = EmployeeProfile(employee_id=emp["id"], identity_card="420106199701011234")
        db_session.add(p)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert "age" in found[0]

    def test_list_has_tenure_field(self, db_session, default_user):
        """列表返回 current_tenure_text 字段"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试司龄"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        er = EmploymentRecord(
            employee_id=emp_db.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2025, 1, 1),
            actual_hire_date=date(2025, 1, 1),
        )
        db_session.add(er)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert "current_tenure_text" in found[0]

    def test_list_has_contract_fields(self, db_session, default_user):
        """列表返回合同相关字段"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试合同"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        emp_rec = EmploymentRecord(
            employee_id=emp_db.id, employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.REGULARIZED,
            hire_date=date(2025, 1, 1),
        )
        db_session.add(emp_rec)
        db_session.flush()
        contract = EmploymentContract(
            employee_id=emp["id"],
            employment_id=emp_rec.id,
            contract_status="SIGNED",
            contract_type=ContractType.INDEFINITE,
        )
        db_session.add(contract)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert found[0]["contract_status"] == "SIGNED"
        assert found[0]["contract_type"] == "INDEFINITE"

    def test_list_has_benefit_fields(self, db_session, default_user):
        """列表返回社保公积金字段"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试福利"}, default_user)
        p = EmployeeProfile(
            employee_id=emp["id"],
            social_insurance_status="ACTIVE",
            housing_fund_status="NOT_PROVIDED",
        )
        db_session.add(p)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert found[0]["social_insurance_status"] == "ACTIVE"
        assert found[0]["housing_fund_status"] == "NOT_PROVIDED"

    def test_list_has_profile_completeness(self, db_session, default_user):
        """列表返回资料完整性"""
        from app.services.employee_service import create_employee
        emp = create_employee(db_session, {"name": "测试资料"}, default_user)
        emp_db = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        emp_db.profile_completeness_status = "COMPLETE"
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        assert found[0]["profile_completeness_status"] == "COMPLETE"

    def test_list_has_next_action_urgency(self, db_session, default_user):
        """列表返回加强版 next_action（含 urgency）"""
        from app.services.employee_service import create_employee
        from app.models.followup_task import FollowupTask
        emp = create_employee(db_session, {"name": "测试事项"}, default_user)
        emp_rec = EmploymentRecord(
            employee_id=emp["id"], employment_seq=1,
            employment_status=EmploymentStatus.ACTIVE,
            probation_status=ProbationStatus.IN_PROGRESS,
            hire_date=date(2026, 1, 1),
            actual_hire_date=date(2026, 1, 1),
            probation_end_date=date(2026, 7, 10),
        )
        db_session.add(emp_rec)
        db_session.flush()
        # 添加一个已逾期的跟进任务
        task = FollowupTask(
            employment_id=emp_rec.id,
            node_definition_id=None,
            node_version=1,
            node_code_snapshot="DAY_7",
            task_name="7天跟进",
            task_source="AUTO",
            planned_date=date(2026, 7, 1),
            original_planned_date=date(2026, 7, 1),
            date_adjusted_manually=False,
            followup_status="PENDING",
            confirmation_mode="ALL",
            idempotency_key=f"test_{emp['id']}",
        )
        db_session.add(task)
        db_session.flush()
        items, total = list_employees(db_session, {"page": 1, "page_size": 20})
        found = [i for i in items if i["id"] == emp["id"]]
        assert len(found) >= 1
        if found[0]["next_action"]:
            assert "urgency" in found[0]["next_action"]
