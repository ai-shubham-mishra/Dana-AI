import asyncio
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from agent.tools.ml_ops.ml.data_prep.combine_low_spend_channels import CombineLowSpendChannelsTool
from integrations.connectors import catalog
from integrations.training.mmm.channel_profile import profile_spend
from integrations.training.mmm.plan import MMMPlan, PreparationSpec, SourceSpec
from integrations.training.mmm.prep import build_rows
from integrations.training.scope import JobScope, bind_scope

MONDAY = date(2024, 1, 1)
WINDOW_END = date(2024, 1, 5)


def combo_plan(channels: list[str], combine: dict[str, list[str]], **changes) -> MMMPlan:
    fields = {
        "kpi": "revenue",
        "channels": channels,
        "controls": ["price"],
        "sources": [
            SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}),
            SourceSpec(table="meta_ads", date_column="date", metrics={"meta_reach": "reach", "meta_traffic": "traffic"}),
        ],
        "date_start": MONDAY,
        "date_end": date(2024, 1, 31),
        "preparation": {"combine_channels": combine},
        "rationale": "Daily revenue with TV and Meta spend.",
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


def test_valid_group_of_outputs_is_accepted():
    plan = combo_plan(["tv", "social"], {"social": ["meta_reach", "meta_traffic"]})
    assert plan.preparation.combine_channels == {"social": ["meta_reach", "meta_traffic"]}


def test_spec_rejects_a_group_with_fewer_than_two_members():
    with pytest.raises(ValidationError, match="at least 2 distinct members"):
        PreparationSpec(combine_channels={"social": ["meta_reach"]})


def test_spec_rejects_an_output_in_two_groups():
    with pytest.raises(ValidationError, match="more than one combined channel"):
        PreparationSpec(combine_channels={"a": ["x", "y"], "b": ["y", "z"]})


def test_plan_rejects_a_member_listed_as_a_channel():
    with pytest.raises(ValidationError, match="combined into a group"):
        combo_plan(["tv", "meta_reach", "social"], {"social": ["meta_reach", "meta_traffic"]})


def test_plan_requires_each_group_to_be_listed_in_channels():
    with pytest.raises(ValidationError, match="must be listed in channels"):
        combo_plan(["tv"], {"social": ["meta_reach", "meta_traffic"]})


def test_plan_rejects_the_kpi_as_a_member():
    with pytest.raises(ValidationError, match="cannot include the kpi"):
        combo_plan(["tv", "social"], {"social": ["revenue", "meta_traffic"]})


def test_plan_rejects_a_control_as_a_member():
    with pytest.raises(ValidationError, match="cannot include control"):
        combo_plan(["tv", "social"], {"social": ["price", "meta_traffic"]})


def test_group_name_cannot_clash_with_an_output():
    with pytest.raises(ValidationError, match="clashes"):
        combo_plan(["tv"], {"tv": ["meta_reach", "meta_traffic"]})


def test_group_name_cannot_clash_with_a_prepared_feature():
    with pytest.raises(ValidationError, match="clashes"):
        combo_plan(["tv", "month"], {"month": ["meta_reach", "meta_traffic"]}, preparation={"date_features": ["month"], "combine_channels": {"month": ["meta_reach", "meta_traffic"]}})


def test_build_rows_sums_members_per_day():
    spec = PreparationSpec(combine_channels={"social": ["meta_reach", "meta_traffic"]})
    by_day = window(MONDAY, date(2024, 1, 3), meta_reach=2.0, meta_traffic=3.0)
    rows, log = build_rows(by_day, ["revenue", "meta_reach", "meta_traffic"], "revenue", MONDAY, date(2024, 1, 3), spec)
    assert [row["social"] for row in rows] == [5.0, 5.0, 5.0]
    assert log["combined"] == {"social": ["meta_reach", "meta_traffic"]}


def test_build_rows_counts_a_blank_member_as_zero():
    spec = PreparationSpec(combine_channels={"social": ["meta_reach", "meta_traffic"]})
    by_day = window(MONDAY, date(2024, 1, 3), meta_reach=2.0, meta_traffic=3.0)
    by_day[date(2024, 1, 2)]["meta_traffic"] = None
    rows, _ = build_rows(by_day, ["revenue", "meta_reach", "meta_traffic"], "revenue", MONDAY, date(2024, 1, 3), spec)
    assert rows[1]["social"] == 2.0
    assert rows[1]["meta_traffic"] == 0.0


def test_profile_flags_low_share_and_unions_active_days_for_groups():
    by_day = {}
    for offset in range(10):
        day = MONDAY + timedelta(days=offset)
        by_day[day] = {
            "big": 100.0,
            "small": 10.0 if offset < 2 else 0.0,
            "tiny": 0.4 if offset == 0 else None,
        }
    by_day[date(2024, 2, 1)] = {"big": 1000.0}
    profile = profile_spend(by_day, ["big", "small", "tiny"], {"combo": ["small", "tiny"]}, MONDAY, date(2024, 1, 10), 0.03)
    assert profile.total_spend == 1020.4
    assert [stat.name for stat in profile.channels] == ["tiny", "small", "big"]
    small = next(stat for stat in profile.channels if stat.name == "small")
    assert small.total == 20.0 and small.active_days == 2 and small.low
    assert not next(stat for stat in profile.channels if stat.name == "big").low
    combo = profile.groups[0]
    assert combo.total == 20.4 and combo.active_days == 2 and combo.low


class FakeCatalog:
    def __init__(self, columns, metric_rows):
        self.columns = columns
        self.metric_rows = metric_rows

    async def get_connector_columns(self, pool, schema, table):
        return self.columns.get(table)

    async def get_daily_metric_rows(self, pool, schema, table, org_id, date_column, metric_columns, start, end, filters=None, text_columns=None):
        return self.metric_rows.get(table, [])


def column(name: str, data_type: str = "numeric") -> dict[str, str]:
    return {"name": name, "data_type": data_type}


@pytest.fixture
def tool(monkeypatch):
    days = [WINDOW_END - timedelta(days=offset) for offset in range(5)]
    columns = {
        "sales_daily": [column("org_id", "text"), column("date", "date"), column("revenue"), column("tv_spend"), column("avg_price")],
        "meta_ads": [column("org_id", "text"), column("date", "date"), column("reach"), column("traffic")],
    }
    metric_rows = {
        "sales_daily": [{"date": day, "values": [10.0, 100.0, 1.0]} for day in days],
        "meta_ads": [{"date": day, "values": [0.5, 0.2]} for day in days],
    }
    fake = FakeCatalog(columns, metric_rows)
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    monkeypatch.setattr(catalog, "get_daily_metric_rows", fake.get_daily_metric_rows)
    return CombineLowSpendChannelsTool(pool=object(), datasets_schema="datasets")


def tool_args(**changes) -> dict:
    args = {
        "sources": [
            {"table": "sales_daily", "date_column": "date", "metrics": {"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}},
            {"table": "meta_ads", "date_column": "date", "metrics": {"meta_reach": "reach", "meta_traffic": "traffic"}},
        ],
        "kpi": "revenue",
        "controls": ["price"],
        "date_start": WINDOW_END - timedelta(days=4),
        "date_end": WINDOW_END,
    }
    args.update(changes)
    return args


def run_tool(tool, args: dict) -> str:
    bind_scope(JobScope(service=object(), org_id="org-a", user_id="user-1", chat_id="chat-1"))
    try:
        return asyncio.run(tool.ainvoke(args))
    finally:
        bind_scope(None)


def test_tool_profiles_and_flags_low_spend_outputs(tool):
    result = run_tool(tool, tool_args())
    lines = result.splitlines()
    assert any(line.startswith("- meta_traffic:") and line.endswith("LOW") for line in lines)
    assert any(line.startswith("- meta_reach:") and line.endswith("LOW") for line in lines)
    assert any(line.startswith("- tv:") and not line.endswith("LOW") for line in lines)
    assert "Profile only" in result


def test_tool_validates_a_proposed_group(tool):
    result = run_tool(tool, tool_args(combine_channels={"social": ["meta_reach", "meta_traffic"]}))
    assert "The groups are valid" in result
    assert "- social:" in result
    assert "Still low and not in a group: none." in result


def test_tool_rejects_the_kpi_inside_a_group(tool):
    result = run_tool(tool, tool_args(combine_channels={"social": ["revenue", "meta_traffic"]}))
    assert "cannot include the kpi" in result
