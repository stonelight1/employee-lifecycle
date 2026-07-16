from datetime import date

from app.services.benefit_parser import parse_benefit_text


def test_parse_benefit_text_known_values():
    today = date(2026, 7, 16)

    hire = parse_benefit_text("五险（入职）", actual_hire_date="2026-07-10", today=today)
    assert hire["social_insurance_policy"] == "FROM_HIRE_DATE"
    assert hire["housing_fund_policy"] == "NOT_PROVIDED"
    assert hire["social_insurance_status"] == "ACTIVE"
    assert hire["social_insurance_start_date"] == "2026-07-10"
    assert hire["housing_fund_start_date"] is None

    regularization = parse_benefit_text(
        " 五险\n（转正） ",
        actual_regularization_date="2026-08-01",
        today=today,
    )
    assert regularization["social_insurance_policy"] == "FROM_REGULARIZATION_DATE"
    assert regularization["social_insurance_status"] == "PENDING"
    assert regularization["housing_fund_status"] == "NOT_PROVIDED"

    both = parse_benefit_text("五险一金(入职)", actual_hire_date="2026-07-10", today=today)
    assert both["social_insurance_policy"] == "FROM_HIRE_DATE"
    assert both["housing_fund_policy"] == "FROM_HIRE_DATE"
    assert both["housing_fund_start_date"] == "2026-07-10"

    none = parse_benefit_text("无", today=today)
    assert none["social_insurance_policy"] == "NOT_PROVIDED"
    assert none["housing_fund_status"] == "NOT_PROVIDED"


def test_parse_benefit_text_blank_and_unrecognized_do_not_guess_policy():
    blank = parse_benefit_text("  ")
    assert blank == {"benefit_parse_status": "BLANK"}

    unknown = parse_benefit_text("后续再定")
    assert unknown["benefit_raw_text"] == "后续再定"
    assert unknown["benefit_parse_status"] == "UNRECOGNIZED"
    assert "social_insurance_policy" not in unknown
    assert "housing_fund_policy" not in unknown
