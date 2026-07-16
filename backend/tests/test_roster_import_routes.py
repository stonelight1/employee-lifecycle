from fastapi.testclient import TestClient
from openpyxl import Workbook
import json

from app.main import app
from app.models.roster_batch import RosterImportBatch
from app.routers.roster_imports import _column_mappings_from_batch


def test_roster_import_routes_do_not_double_prefix_api():
    client = TestClient(app)

    assert client.get("/api/roster-imports/field-definitions").status_code == 200
    assert client.get("/api/api/roster-imports/field-definitions").status_code == 404


def test_roster_import_static_routes_precede_batch_id_route():
    client = TestClient(app)

    response = client.get("/api/roster-imports/field-definitions")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_roster_upload_exposes_editable_column_mappings_and_preview_rows(tmp_path):
    workbook = Workbook()
    ws = workbook.active
    ws.title = "员工花名册-总表"
    ws.append(["序号", "姓名", "入职时间", "五险一金缴纳"])
    ws.append([1, "张三", 42891, "五险一金（入职）"])
    file_path = tmp_path / "roster.xlsx"
    workbook.save(file_path)

    client = TestClient(app)
    with file_path.open("rb") as f:
        upload_response = client.post(
            "/api/roster-imports/upload",
            files={
                "file": (
                    "roster.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"mode": "SYNC"},
        )

    assert upload_response.status_code == 200
    batch_id = upload_response.json()["data"]["batch_id"]

    detail_response = client.get(f"/api/roster-imports/{batch_id}")
    assert detail_response.status_code == 200
    mappings = detail_response.json()["data"]["column_mappings"]
    assert any(
        mapping["source_header"] == "姓名" and mapping["target_field_key"] == "name"
        for mapping in mappings
    )
    assert any(
        mapping["source_header"] == "五险一金缴纳"
        and mapping["target_field_key"] == "benefit_raw_text"
        for mapping in mappings
    )

    save_response = client.post(
        f"/api/roster-imports/{batch_id}/mapping",
        json={
            "mappings": {
                "序号": None,
                "姓名": "name",
                "入职时间": "hire_date",
                "五险一金缴纳": "benefit_raw_text",
            }
        },
    )
    assert save_response.status_code == 200

    rows_response = client.get(f"/api/roster-imports/{batch_id}/rows")
    assert rows_response.status_code == 200
    row = rows_response.json()["data"]["items"][0]
    assert row["normalized_data"]["hire_date"] == "2017-06-05"
    assert row["normalized_data"]["benefit_raw_text"] == "五险一金(入职)"
    assert row["normalized_data"]["social_insurance_policy"] == "FROM_HIRE_DATE"
    assert row["normalized_data"]["housing_fund_policy"] == "FROM_HIRE_DATE"
    assert row["normalized_data"]["social_insurance_status"] == "ACTIVE"
    assert row["normalized_data"]["housing_fund_start_date"] == "2017-06-05"

    preview_response = client.post(f"/api/roster-imports/{batch_id}/preview")
    assert preview_response.status_code == 200
    preview_data = preview_response.json()["data"]
    assert preview_data["summary"]["total_rows"] == 1
    assert preview_data["rows"][0]["normalized_name"] == "张三"

    detail_response = client.get(f"/api/roster-imports/{batch_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["batch_status"] == "READY"

    commit_response = client.post(f"/api/roster-imports/{batch_id}/commit")
    assert commit_response.status_code == 200
    commit_data = commit_response.json()["data"]
    assert commit_data["status"] == "SUCCEEDED"
    assert commit_data["message"] == "导入已完成"


def test_batch_detail_backfills_current_aliases_for_old_unmapped_headers():
    batch = RosterImportBatch(
        batch_no="BATCH-OLD-MAPPING",
        file_name="roster.xlsx",
        stored_file_path="roster.xlsx",
        file_sha256="0" * 64,
        file_size=1,
        header_row=json.dumps(
            [
                {"header": "姓名", "field_key": "name"},
                {"header": "五险一金缴纳", "field_key": None},
            ],
            ensure_ascii=False,
        ),
    )

    mappings = _column_mappings_from_batch(batch)

    assert any(
        mapping["source_header"] == "五险一金缴纳"
        and mapping["target_field_key"] == "benefit_raw_text"
        and mapping["is_mapped"] is True
        for mapping in mappings
    )
