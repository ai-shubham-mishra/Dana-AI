import asyncio
from datetime import date

import pytest

from agent.tools.registry import TOOLS
from agent.tools.system_ops.calendar.resolve_date_range import resolve_range
from agent.tools.system_ops.utilities.calculate import calculate

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
TODAY = date(2026, 9, 28)


def run(name: str, **args):
    return asyncio.run(TOOLS_BY_NAME[name].ainvoke(args))


def test_new_tools_are_registered():
    assert {"get_current_date", "resolve_date_range", "get_calendar_events", "calculate"} <= TOOLS_BY_NAME.keys()


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("last 12 months", (date(2025, 9, 28), TODAY)),
        ("Last 3 Quarters", (date(2025, 12, 28), TODAY)),
        ("last 30 days", (date(2026, 8, 29), TODAY)),
        ("last 2 weeks", (date(2026, 9, 14), TODAY)),
        ("this year", (date(2026, 1, 1), TODAY)),
        ("year to date", (date(2026, 1, 1), TODAY)),
        ("last year", (date(2025, 1, 1), date(2025, 12, 31))),
        ("this month", (date(2026, 9, 1), TODAY)),
        ("last month", (date(2026, 8, 1), date(2026, 8, 31))),
        ("this quarter", (date(2026, 7, 1), TODAY)),
        ("last quarter", (date(2026, 4, 1), date(2026, 6, 30))),
        ("last week", (date(2026, 9, 21), date(2026, 9, 27))),
        ("2024-01-01 to 2024-12-31", (date(2024, 1, 1), date(2024, 12, 31))),
    ],
)
def test_resolve_range_phrases(phrase, expected):
    assert resolve_range(phrase, TODAY) == expected


def test_resolve_range_rejects_unknown_phrase_and_reversed_dates():
    with pytest.raises(ValueError, match="Supported phrases"):
        resolve_range("sometime soon", TODAY)
    with pytest.raises(ValueError, match="after the end date"):
        resolve_range("2024-12-31 to 2024-01-01", TODAY)


def test_resolve_date_range_tool_returns_training_format():
    result = run("resolve_date_range", phrase="last 12 months", timezone="Asia/Kolkata")
    start, end = result.split(" to ")
    assert date.fromisoformat(start) < date.fromisoformat(end)


def test_resolve_date_range_tool_reports_error_for_bad_timezone():
    assert run("resolve_date_range", phrase="this year", timezone="Mars/Olympus").startswith("Error: Unknown timezone")


def test_get_current_date_uses_requested_timezone():
    result = run("get_current_date", timezone="Asia/Kolkata")
    assert "+05:30" in result and "Asia/Kolkata" in result


def test_get_current_date_rejects_unknown_timezone():
    assert run("get_current_date", timezone="Not/AZone").startswith("Error: Unknown timezone")


def test_calendar_lists_public_holidays_and_retail_dates():
    result = run("get_calendar_events", country="IN", start_date="2026-01-01", end_date="2026-01-31")
    assert "2026-01-26 Mon Republic Day (public holiday)" in result


def test_calendar_retail_dates_for_us():
    result = run("get_calendar_events", country="US", start_date="2026-11-01", end_date="2026-11-30", event_type="retail")
    assert "2026-11-27 Fri Black Friday (retail)" in result
    assert "2026-11-30 Mon Cyber Monday (retail)" in result
    assert "public holiday" not in result


def test_calendar_event_type_filters_out_retail():
    result = run("get_calendar_events", country="US", start_date="2026-11-01", end_date="2026-11-30", event_type="public_holiday")
    assert "Black Friday" not in result
    assert "Thanksgiving" in result


def test_calendar_rejects_bad_window_and_unknown_country():
    assert run("get_calendar_events", country="US", start_date="2026-02-01", end_date="2026-01-01").startswith("Error:")
    assert run("get_calendar_events", country="US", start_date="2000-01-01", end_date="2026-01-01").startswith("Error:")
    assert run("get_calendar_events", country="ZZ", start_date="2026-01-01", end_date="2026-01-31").startswith("Error:")


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("2 + 3 * 4", 14),
        ("(1250000 - 980000) / 980000 * 100", 27.55102040816327),
        ("2 ** 10", 1024),
        ("-7 // 2", -4),
        ("sqrt(144) + max(3, 9)", 21),
        ("round(pi, 2)", 3.14),
        ("log10(1000)", 3),
    ],
)
def test_calculate_evaluates_arithmetic(expression, value):
    assert calculate(expression) == pytest.approx(value)


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').system('echo hi')", "open('/etc/passwd')", "1 +", "2 ** 100000", "(-8) ** 0.5", "1 / 0", "x + 1", "True + 1"],
)
def test_calculate_rejects_unsafe_or_invalid_input(expression):
    assert run("calculate", expression=expression).startswith("Error:")


def test_calculate_tool_reports_result():
    assert run("calculate", expression="pi * 2") == "pi * 2 = 6.283185307"
