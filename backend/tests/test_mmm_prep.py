from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from integrations.training.mmm.plan import MMMPlan, PreparationSpec, SourceSpec
from integrations.training.mmm.prep import build_rows

MONDAY = date(2024, 1, 1)
SATURDAY = date(2024, 1, 6)


def make_plan(preparation: dict | None = None, **changes) -> MMMPlan:
    fields = {
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": [
            SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}),
            SourceSpec(table="google_ads", date_column="date", metrics={"search": "search_spend"}),
        ],
        "date_start": MONDAY,
        "date_end": date(2024, 1, 31),
        "preparation": preparation or {},
        "rationale": "Daily revenue with TV and search spend.",
    }
    fields.update(changes)
    return MMMPlan(**fields)


def window(start: date, end: date, **values: float | None) -> dict[date, dict[str, float | None]]:
    days = {}
    current = start
    while current <= end:
        days[current] = {"revenue": 10.0, **values}
        current += timedelta(days=1)
    return days


def test_spec_defaults_are_empty_and_add_no_features():
    spec = PreparationSpec()
    assert spec.is_empty()
    assert spec.feature_names() == []
    assert spec.history_days() == 0


def test_spec_lists_features_and_history_in_order():
    spec = PreparationSpec(date_features=["month"], holiday_country="US", lags={"search": [7, 14]}, rolling_means={"search": 7})
    assert spec.feature_names() == ["month", "is_holiday", "search_lag_7", "search_lag_14", "search_roll_mean_7"]
    assert spec.history_days() == 14
    assert not spec.is_empty()


@pytest.mark.parametrize(
    "preparation, message",
    [
        ({"holiday_country": "XX"}, "not supported"),
        ({"lags": {"search": [0]}}, "between 1 and 52"),
        ({"lags": {"search": [53]}}, "between 1 and 52"),
        ({"lags": {"search": []}}, "non-empty"),
        ({"rolling_means": {"search": 1}}, "between 2 and 52"),
        ({"date_features": ["month", "month"]}, "must not repeat"),
        ({"text_to_numeric": ["search", "search"]}, "must not repeat"),
        ({"lags": {"Search": [7]}}, "snake_case"),
    ],
)
def test_spec_rejects_bad_preparation(preparation, message):
    with pytest.raises(ValidationError, match=message):
        PreparationSpec(**preparation)


@pytest.mark.parametrize(
    "preparation, message",
    [
        ({"lags": {"revenue": [7]}}, "leak the target"),
        ({"rolling_means": {"revenue": 7}}, "leak the target"),
        ({"text_to_numeric": ["promo"]}, "is not a mapped output"),
        ({"lags": {"promo": [7]}}, "is not a mapped output"),
    ],
)
def test_plan_checks_preparation_against_mapped_outputs(preparation, message):
    with pytest.raises(ValidationError, match=message):
        make_plan(preparation)


def test_plan_accepts_valid_preparation_for_mapped_outputs():
    plan = make_plan({"date_features": ["month"], "lags": {"search": [1]}, "text_to_numeric": ["search"]})
    assert "search_lag_1" in plan.preparation.feature_names()



def test_prepared_feature_cannot_clash_with_an_output():
    with pytest.raises(ValidationError, match="clashes with a mapped output"):
        make_plan({"date_features": ["month"]}, sources=[
            SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue", "month": "tv_spend", "price": "avg_price"}),
            SourceSpec(table="google_ads", date_column="date", metrics={"search": "search_spend"}),
        ], channels=["month", "search"], controls=["price"])


def test_calendar_features_follow_the_date():
    by_day = window(MONDAY, SATURDAY, search=1.0)
    rows, _ = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, SATURDAY, PreparationSpec(date_features=["day_of_week", "month", "week_of_year", "is_weekend"]))
    monday, saturday = rows[0], rows[-1]
    assert (monday["day_of_week"], monday["month"], monday["week_of_year"], monday["is_weekend"]) == (0, 1, 1, 0)
    assert (saturday["day_of_week"], saturday["is_weekend"]) == (5, 1)


def test_holiday_flag_marks_public_holidays():
    by_day = window(MONDAY, date(2024, 1, 2), search=1.0)
    rows, _ = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, date(2024, 1, 2), PreparationSpec(holiday_country="US"))
    assert [row["is_holiday"] for row in rows] == [1, 0]


def test_lags_read_history_before_the_window():
    history_start = MONDAY - timedelta(days=7)
    by_day = window(history_start, date(2024, 1, 3), search=5.0)
    by_day[history_start]["search"] = 100.0
    rows, log = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, date(2024, 1, 3), PreparationSpec(lags={"search": [7]}))
    assert rows[0]["search_lag_7"] == 100.0
    assert log["history_days"] == 7
    assert log["rows_kept"] == 3


def test_rolling_mean_uses_the_trailing_window():
    dec_30, dec_31 = MONDAY - timedelta(days=2), MONDAY - timedelta(days=1)
    by_day = window(dec_30, MONDAY, search=0.0)
    by_day[dec_30]["search"] = 3.0
    by_day[dec_31]["search"] = 6.0
    by_day[MONDAY]["search"] = 9.0
    rows, _ = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, MONDAY, PreparationSpec(rolling_means={"search": 3}))
    assert rows[0]["search_roll_mean_3"] == 6.0


def test_blanks_are_counted_and_filled_with_zero():
    by_day = window(MONDAY, date(2024, 1, 3), search=None)
    by_day[date(2024, 1, 2)]["search"] = 4.0
    rows, log = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, date(2024, 1, 3), PreparationSpec())
    assert [row["search"] for row in rows] == [0.0, 4.0, 0.0]
    assert log["blanks_filled"] == {"revenue": 0, "search": 2}


def test_days_without_a_kpi_row_are_dropped_and_counted():
    by_day = window(MONDAY, date(2024, 1, 4), search=1.0)
    del by_day[date(2024, 1, 2)]["revenue"]
    rows, log = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, date(2024, 1, 4), PreparationSpec())
    assert [row["date"] for row in rows] == ["2024-01-01", "2024-01-03", "2024-01-04"]
    assert log["days_dropped_without_kpi"] == 1


def test_days_outside_the_window_are_not_returned():
    by_day = window(MONDAY - timedelta(days=3), date(2024, 1, 5), search=1.0)
    rows, _ = build_rows(by_day, ["revenue", "search"], "revenue", MONDAY, date(2024, 1, 2), PreparationSpec())
    assert [row["date"] for row in rows] == ["2024-01-01", "2024-01-02"]
