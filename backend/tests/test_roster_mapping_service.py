"""
花名册字段映射服务测试 —— ROSTER-MAP-001 ~ ROSTER-MAP-006
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.exceptions import Conflict, ResourceNotFound
from app.models.roster_batch import RosterImportBatch
from app.models.roster_alias import RosterColumnAlias
from app.models.roster_value_alias import RosterValueAlias
from app.services.roster_mapping_service import (
    auto_detect_mappings,
    create_column_alias,
    create_value_alias,
    get_field_definitions,
    get_mapping_for_batch,
    list_column_aliases,
    list_value_aliases,
    resolve_value_alias,
    save_mapping,
)


# ─── 测试辅助函数 ────────────────────────────────────────────────────────────


def _create_batch(
    db: Session,
    **overrides: Any,
) -> RosterImportBatch:
    """创建测试用批次记录。"""
    defaults = {
        "batch_no": f"BT-{uuid.uuid4().hex[:8].upper()}",
        "file_name": "test_roster.xlsx",
        "stored_file_path": "/tmp/test_roster.xlsx",
        "file_sha256": "0" * 64,
        "file_size": 1024,
        "mode": "SYNC",
        "batch_status": "UPLOADED",
        "sheet_name": "Sheet1",
        "header_row": "[]",
        "total_rows": 0,
    }
    defaults.update(overrides)
    batch = RosterImportBatch(**defaults)
    db.add(batch)
    db.flush()
    return batch


# ─── 自动检测映射 ────────────────────────────────────────────────────────────


class TestAutoDetectMappings:
    """ROSTER-MAP-001 自动检测列映射"""

    def test_all_known_headers(self):
        """常见表头全部自动匹配"""
        headers = ["姓名", "手机号", "部门", "岗位", "邮箱"]
        result = auto_detect_mappings(headers)
        assert result["姓名"] == "name"
        assert result["手机号"] == "mobile"
        assert result["部门"] == "department"
        assert result["岗位"] == "position"
        assert result["邮箱"] == "email"

    def test_all_unknown_headers(self):
        """完全未知的表头 -> 全部 None"""
        headers = ["col1", "col2", "col3"]
        result = auto_detect_mappings(headers)
        assert all(v is None for v in result.values())

    def test_mixed_known_and_unknown(self):
        """混合已知和未知表头"""
        headers = ["姓名", "some_random_col"]
        result = auto_detect_mappings(headers)
        assert result["姓名"] == "name"
        assert result["some_random_col"] is None

    def test_empty_headers(self):
        """空表头列表"""
        result = auto_detect_mappings([])
        assert result == {}

    def test_skip_columns_excluded(self):
        """__skip__ 列的 field_key 应为 None (不对外暴露 __skip__)"""
        headers = ["证件类型", "序号"]
        result = auto_detect_mappings(headers)
        assert result["证件类型"] is None
        assert result["序号"] is None

    def test_normalize_strips_suffix(self):
        """含常见后缀的表头仍能匹配"""
        headers = ["姓名（必填）", "手机号/说明"]
        result = auto_detect_mappings(headers)
        assert result["姓名（必填）"] == "name"
        assert result["手机号/说明"] == "mobile"

    def test_prefix_stripping(self):
        """含常见前缀的表头仍能匹配"""
        headers = ["员工姓名", "人员类型"]
        result = auto_detect_mappings(headers)
        assert result["员工姓名"] == "name"
        assert result["人员类型"] == "employment_type"

    def test_fuzzy_match_high_similarity(self):
        """模糊匹配 (相似度 >= 0.6)"""
        headers = ["手号机"]
        result = auto_detect_mappings(headers)
        # "手号机" 与 "手机号" 编辑距离较小，应模糊匹配
        assert result["手号机"] == "mobile"

    def test_variant_headers(self):
        """各种别名变体"""
        mapping = {
            "姓名": "name",
            "员工姓名": "name",
            "名称": "name",
            "名字": "name",
            "员工名称": "name",
            "员工名字": "name",
        }
        headers = list(mapping.keys())
        result = auto_detect_mappings(headers)
        for header, expected_key in mapping.items():
            assert result[header] == expected_key, f"'{header}' 应映射为 {expected_key}"

    def test_actual_roster_headers(self):
        """当前花名册里的业务表头应自动匹配"""
        headers = ["是否在职", "用工形式", "现底薪（默认含30kpi）", "五险一金缴纳"]
        result = auto_detect_mappings(headers)
        assert result["是否在职"] == "employment_status"
        assert result["用工形式"] == "employment_type"
        assert result["现底薪（默认含30kpi）"] == "raw_salary_text"
        assert result["五险一金缴纳"] == "benefit_raw_text"

    def test_phone_variants(self):
        """手机号的各种变体"""
        headers = ["手机号码", "手机号", "电话号码", "联系电话", "电话", "手机", "移动电话"]
        result = auto_detect_mappings(headers)
        for header in headers:
            assert result[header] == "mobile", f"'{header}' 应映射为 mobile"

    def test_department_variants(self):
        """部门的各种变体"""
        headers = ["部门", "所属部门", "部门名称"]
        result = auto_detect_mappings(headers)
        for header in headers:
            assert result[header] == "department", f"'{header}' 应映射为 department"

    def test_position_variants(self):
        """岗位的各种变体"""
        headers = ["岗位", "职位", "工作岗位", "岗位名称", "职务"]
        result = auto_detect_mappings(headers)
        for header in headers:
            assert result[header] == "position", f"'{header}' 应映射为 position"

    def test_empty_header_string(self):
        """空字符串表头 -> None"""
        result = auto_detect_mappings([""])
        assert result[""] is None

    def test_whitespace_header(self):
        """空白表头 -> None"""
        result = auto_detect_mappings(["  "])
        assert result["  "] is None

    def test_date_header_mapped_to_skip(self):
        """日期格式列 -> None (__skip__)"""
        result = auto_detect_mappings(["入职月份", "入职年份"])
        assert result["入职月份"] is None
        assert result["入职年份"] is None


# ─── 保存与查询映射 ─────────────────────────────────────────────────────────


class TestSaveAndGetMapping:
    """ROSTER-MAP-002 保存与查询列映射"""

    def test_save_mapping(self, db_session):
        """保存列映射到批次记录"""
        batch = _create_batch(db_session)
        mappings = {"姓名": "name", "手机号": "mobile", "无用列": None}

        result = save_mapping(db_session, batch.id, mappings, "test-hr")

        assert result["id"] == batch.id
        assert result["updated_by"] == "test-hr"
        assert result["updated_at"] is not None

    def test_get_mapping(self, db_session):
        """获取批次已保存的列映射"""
        batch = _create_batch(db_session)
        mappings = {"姓名": "name", "部门": "department"}
        save_mapping(db_session, batch.id, mappings, "test-hr")

        result = get_mapping_for_batch(db_session, batch.id)

        assert result["batch_id"] == batch.id
        assert result["mappings"]["姓名"] == "name"
        assert result["mappings"]["部门"] == "department"
        assert result["total_columns"] == 2
        assert result["mapped_count"] == 2

    def test_get_mapping_with_none_values(self, db_session):
        """None 值的列计入 total 但不计入 mapped_count"""
        batch = _create_batch(db_session)
        mappings = {"姓名": "name", "未知列": None, "手机号": "mobile"}
        save_mapping(db_session, batch.id, mappings, "test-hr")

        result = get_mapping_for_batch(db_session, batch.id)
        assert result["total_columns"] == 3
        assert result["mapped_count"] == 2

    def test_save_mapping_nonexistent_batch(self, db_session):
        """批次不存在 -> ResourceNotFound"""
        with pytest.raises(ResourceNotFound):
            save_mapping(db_session, 99999, {}, "test-hr")

    def test_get_mapping_nonexistent_batch(self, db_session):
        """查询不存在的批次 -> ResourceNotFound"""
        with pytest.raises(ResourceNotFound):
            get_mapping_for_batch(db_session, 99999)

    def test_save_mapping_creates_column_alias_for_unknown_key(self, db_session):
        """未知 field_key 自动创建列别名"""
        batch = _create_batch(db_session)
        mappings = {"自定义字段": "custom_field"}
        save_mapping(db_session, batch.id, mappings, "test-hr")
        db_session.flush()  # save_mapping 中未 flush 新创建的别名

        aliases = list_column_aliases(db_session)
        alias_headers = [a["source_header_normalized"] for a in aliases]
        assert "自定义字段" in alias_headers

    def test_save_mapping_skips_existing_column_alias(self, db_session):
        """已存在的列别名不重复创建"""
        # 先手动创建列别名
        create_column_alias(
            db_session,
            {"source_header": "自定义字段", "target_field_key": "custom_field", "created_by": "tester"},
        )
        alias_count_before = len(list_column_aliases(db_session))

        batch = _create_batch(db_session)
        mappings = {"自定义字段": "custom_field"}
        save_mapping(db_session, batch.id, mappings, "test-hr")

        alias_count_after = len(list_column_aliases(db_session))
        assert alias_count_after == alias_count_before

    def test_save_mapping_skips_standard_field_keys(self, db_session):
        """标准 field_key 不创建列别名"""
        batch = _create_batch(db_session)
        mappings = {"姓名": "name", "部门": "department"}
        save_mapping(db_session, batch.id, mappings, "test-hr")

        aliases = list_column_aliases(db_session)
        assert len(aliases) == 0

    def test_get_mapping_returns_mapping_list(self, db_session):
        """get_mapping_for_batch 返回 mapping_list 字段"""
        batch = _create_batch(db_session)
        mappings = {"姓名": "name"}
        save_mapping(db_session, batch.id, mappings, "test-hr")

        result = get_mapping_for_batch(db_session, batch.id)
        assert "mapping_list" in result
        assert len(result["mapping_list"]) == 1
        assert result["mapping_list"][0]["header"] == "姓名"
        assert result["mapping_list"][0]["field_key"] == "name"


# ─── 列别名管理 ──────────────────────────────────────────────────────────────


class TestColumnAlias:
    """ROSTER-MAP-003 列别名管理"""

    def test_create_column_alias(self, db_session):
        """创建列别名"""
        data = {
            "source_header": "自定义字段",
            "target_field_key": "custom_field",
            "created_by": "test-hr",
        }
        result = create_column_alias(db_session, data)

        assert result["source_header_normalized"] == "自定义字段"
        assert result["target_field_key"] == "custom_field"
        assert result["enabled"] is True
        assert result["id"] is not None

    def test_create_column_alias_normalizes_header(self, db_session):
        """表头被标准化存储"""
        data = {
            "source_header": "  自定义字段  ",
            "target_field_key": "custom_field",
        }
        result = create_column_alias(db_session, data)
        assert result["source_header_normalized"] == "自定义字段"

    def test_create_column_alias_duplicate(self, db_session):
        """重复创建相同标准化表头 -> Conflict"""
        data = {
            "source_header": "自定义字段",
            "target_field_key": "custom_field",
        }
        create_column_alias(db_session, data)
        with pytest.raises(Conflict) as exc:
            create_column_alias(db_session, data)
        assert "列别名已存在" in str(exc.value)

    def test_create_column_alias_duplicate_normalized(self, db_session):
        """标准化后相同也视为重复"""
        create_column_alias(
            db_session, {"source_header": "自定义字段", "target_field_key": "f1"}
        )
        with pytest.raises(Conflict):
            create_column_alias(
                db_session, {"source_header": "  自定义字段  ", "target_field_key": "f2"}
            )

    def test_create_column_alias_empty_header(self, db_session):
        """空 source_header -> ValueError"""
        with pytest.raises(ValueError):
            create_column_alias(db_session, {"source_header": "", "target_field_key": "f"})

    def test_create_column_alias_none_header(self, db_session):
        """None 或仅空白的 source_header -> ValueError"""
        with pytest.raises(ValueError):
            create_column_alias(db_session, {"source_header": "  ", "target_field_key": "f"})

    def test_create_column_alias_empty_field_key(self, db_session):
        """空 target_field_key -> ValueError"""
        with pytest.raises(ValueError):
            create_column_alias(db_session, {"source_header": "h", "target_field_key": ""})

    def test_create_column_alias_default_enabled(self, db_session):
        """enabled 默认 True"""
        result = create_column_alias(
            db_session, {"source_header": "new_col", "target_field_key": "new"}
        )
        assert result["enabled"] is True

    def test_create_column_alias_disabled(self, db_session):
        """可显式设置 enabled=False"""
        result = create_column_alias(
            db_session,
            {"source_header": "disabled_col", "target_field_key": "discard", "enabled": False},
        )
        assert result["enabled"] is False

    def test_list_column_aliases(self, db_session):
        """列出所有列别名"""
        create_column_alias(db_session, {"source_header": "A", "target_field_key": "a"})
        create_column_alias(db_session, {"source_header": "B", "target_field_key": "b"})
        aliases = list_column_aliases(db_session)
        assert len(aliases) == 2

    def test_list_column_aliases_empty(self, db_session):
        """无列别名时返回空列表"""
        aliases = list_column_aliases(db_session)
        assert aliases == []

    def test_list_column_aliases_ordered_by_id(self, db_session):
        """按 id 升序排列"""
        create_column_alias(db_session, {"source_header": "second", "target_field_key": "b"})
        create_column_alias(db_session, {"source_header": "first", "target_field_key": "a"})
        aliases = list_column_aliases(db_session)
        ids = [a["id"] for a in aliases]
        assert ids == sorted(ids)


# ─── 值别名管理 ──────────────────────────────────────────────────────────────


class TestValueAlias:
    """ROSTER-MAP-004 值别名管理"""

    def test_create_value_alias(self, db_session):
        """创建值别名"""
        data = {
            "field_key": "gender",
            "source_value": "男",
            "target_value": "MALE",
            "created_by": "test-hr",
        }
        result = create_value_alias(db_session, data)

        assert result["field_key"] == "gender"
        assert result["source_value_normalized"] == "男"
        assert result["target_value"] == "MALE"
        assert result["id"] is not None

    def test_create_value_alias_normalizes_source(self, db_session):
        """source_value 被标准化存储"""
        result = create_value_alias(
            db_session, {"field_key": "gender", "source_value": "  男  ", "target_value": "MALE"}
        )
        assert result["source_value_normalized"] == "男"

    def test_create_value_alias_duplicate(self, db_session):
        """重复 (field_key, source_value_normalized) -> Conflict"""
        data = {"field_key": "gender", "source_value": "男", "target_value": "MALE"}
        create_value_alias(db_session, data)
        with pytest.raises(Conflict) as exc:
            create_value_alias(db_session, data)
        assert "值别名已存在" in str(exc.value)

    def test_create_value_alias_duplicate_normalized(self, db_session):
        """标准化后相同也视为重复"""
        create_value_alias(
            db_session, {"field_key": "gender", "source_value": "女", "target_value": "FEMALE"}
        )
        with pytest.raises(Conflict):
            create_value_alias(
                db_session,
                {"field_key": "gender", "source_value": "  女  ", "target_value": "FEMALE"},
            )

    def test_create_value_alias_same_value_different_field(self, db_session):
        """不同 field_key 允许相同 source_value"""
        a = create_value_alias(
            db_session, {"field_key": "gender", "source_value": "男", "target_value": "M"}
        )
        b = create_value_alias(
            db_session, {"field_key": "other", "source_value": "男", "target_value": "MAN"}
        )
        assert a["id"] != b["id"]

    def test_create_value_alias_empty_field_key(self, db_session):
        """空 field_key -> ValueError"""
        with pytest.raises(ValueError):
            create_value_alias(db_session, {"field_key": "", "source_value": "v", "target_value": "t"})

    def test_create_value_alias_empty_source(self, db_session):
        """空 source_value -> ValueError"""
        with pytest.raises(ValueError):
            create_value_alias(db_session, {"field_key": "k", "source_value": "  ", "target_value": "t"})

    def test_create_value_alias_empty_target(self, db_session):
        """空 target_value -> ValueError"""
        with pytest.raises(ValueError):
            create_value_alias(db_session, {"field_key": "k", "source_value": "v", "target_value": ""})


class TestResolveValueAlias:
    """ROSTER-MAP-005 值别名解析"""

    def test_resolve_exact_match(self, db_session):
        """精确匹配返回 target_value"""
        create_value_alias(
            db_session, {"field_key": "employment_type", "source_value": "正式", "target_value": "FORMAL"}
        )
        result = resolve_value_alias(db_session, "employment_type", "正式")
        assert result == "FORMAL"

    def test_resolve_normalized_match(self, db_session):
        """标准化后匹配 (空白处理)"""
        create_value_alias(
            db_session, {"field_key": "employment_type", "source_value": " 正式 ", "target_value": "FORMAL"}
        )
        result = resolve_value_alias(db_session, "employment_type", "正式")
        assert result == "FORMAL"

    def test_resolve_no_match(self, db_session):
        """无匹配返回 None"""
        result = resolve_value_alias(db_session, "gender", "未知")
        assert result is None

    def test_resolve_empty_value(self, db_session):
        """空 source_value -> None"""
        result = resolve_value_alias(db_session, "gender", "")
        assert result is None

    def test_resolve_whitespace_value(self, db_session):
        """空白 source_value -> None"""
        result = resolve_value_alias(db_session, "gender", "  ")
        assert result is None

    def test_resolve_wrong_field_key(self, db_session):
        """不同 field_key 不匹配"""
        create_value_alias(
            db_session, {"field_key": "type_a", "source_value": "x", "target_value": "y"}
        )
        result = resolve_value_alias(db_session, "type_b", "x")
        assert result is None

    def test_resolve_preserves_target_case(self, db_session):
        """返回的 target_value 保持原始大小写"""
        create_value_alias(
            db_session, {"field_key": "test", "source_value": "abc", "target_value": "TargetValue"}
        )
        result = resolve_value_alias(db_session, "test", "abc")
        assert result == "TargetValue"


class TestListValueAlias:
    """ROSTER-MAP-006 值别名列表查询"""

    def test_list_all(self, db_session):
        """列出所有值别名"""
        create_value_alias(db_session, {"field_key": "a", "source_value": "v1", "target_value": "t1"})
        create_value_alias(db_session, {"field_key": "b", "source_value": "v2", "target_value": "t2"})
        aliases = list_value_aliases(db_session)
        assert len(aliases) == 2

    def test_list_filtered_by_field_key(self, db_session):
        """按 field_key 过滤"""
        create_value_alias(db_session, {"field_key": "gender", "source_value": "男", "target_value": "M"})
        create_value_alias(db_session, {"field_key": "gender", "source_value": "女", "target_value": "F"})
        create_value_alias(db_session, {"field_key": "type", "source_value": "正式", "target_value": "F"})

        aliases = list_value_aliases(db_session, field_key="gender")
        assert len(aliases) == 2
        assert all(a["field_key"] == "gender" for a in aliases)

    def test_list_filtered_empty_result(self, db_session):
        """过滤不存在 field_key -> 空列表"""
        create_value_alias(db_session, {"field_key": "a", "source_value": "v", "target_value": "t"})
        aliases = list_value_aliases(db_session, field_key="nonexistent")
        assert aliases == []

    def test_list_empty(self, db_session):
        """无值别名 -> 空列表"""
        assert list_value_aliases(db_session) == []


# ─── 字段定义 ────────────────────────────────────────────────────────────────


class TestFieldDefinitions:
    """ROSTER-MAP-007 字段定义查询"""

    def test_get_field_definitions_returns_list(self):
        """返回列表"""
        definitions = get_field_definitions()
        assert isinstance(definitions, list)

    def test_get_field_definitions_contains_required_fields(self):
        """包含所有必填字段"""
        definitions = get_field_definitions()
        keys = {d["key"] for d in definitions}
        assert "name" in keys
        assert "mobile" in keys
        assert "department" in keys
        assert "position" in keys
        assert "hire_date" in keys

    def test_get_field_definitions_structure(self):
        """每个字段定义包含完整结构"""
        definitions = get_field_definitions()
        for field in definitions:
            assert "key" in field
            assert "label" in field
            assert "required" in field
            assert "description" in field
            assert "example_values" in field

    def test_name_is_required(self):
        """姓名字段为必填"""
        definitions = get_field_definitions()
        name_def = next(d for d in definitions if d["key"] == "name")
        assert name_def["required"] is True

    def test_most_fields_optional(self):
        """大多数字段为非必填"""
        definitions = get_field_definitions()
        non_required = [d for d in definitions if not d["required"]]
        assert len(non_required) == len(definitions) - 1  # 仅 name 为必填

    def test_definitions_immutable(self):
        """每次调用返回新列表 (浅拷贝容器)"""
        d1 = get_field_definitions()
        d2 = get_field_definitions()
        assert d1 is not d2  # 列表对象不同

    def test_get_field_definitions_has_labels(self):
        """所有字段定义有中文标签"""
        definitions = get_field_definitions()
        for field in definitions:
            assert field["label"], f"字段 {field['key']} 缺少 label"
