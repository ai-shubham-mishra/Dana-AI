import ast
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.tools.ml_ops.ml.training.start_mmm_run import START_MMM_RUN_TOOL, StartMmmRunTool
from agent.tools.registry import STATIC_TOOLS
from integrations.connectors import catalog
from integrations.training.mmm.dataset import MIN_ROWS, build_dataset, validate_sources
from integrations.training.mmm.plan import MMMPlan, PlanError, SourceSpec
from integrations.training.mmm.recipe import build_config, dump_config, load_defaults, render_script
from integrations.training.mmm.run_folder import RUN_FILES, missing_outputs, write_inputs
from integrations.training.mmm.sandbox import SandboxError, run_script, sandbox_env
from integrations.training.scope import JobScope, bind_scope

ORG_A = "org-a"
START = date(2024, 1, 1)
END = date(2024, 12, 31)


def make_plan(**changes) -> MMMPlan:
    fields = {
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": [
            SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}),
            SourceSpec(table="google_ads", date_column="date", metrics={"search": "search_spend"}),
        ],
        "date_start": START,
        "date_end": END,
        "overrides": {},
        "rationale": "Weekly-grain revenue with TV and search spend.",
    }
    fields.update(changes)
    return MMMPlan(**fields)


def test_valid_plan_passes_and_lists_outputs():
    plan = make_plan()
    assert plan.output_names() == ["revenue", "tv", "price", "search"]


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"sources": [SourceSpec(table="t", date_column="date", metrics={"date": "x", "revenue": "r"})]}, "reserved"),
        ({"sources": [SourceSpec(table="t", date_column="date", metrics={"Revenue": "r"})]}, "snake_case"),
        ({"kpi": "sales"}, "not a mapped output"),
        ({"controls": ["tv"]}, "must not overlap"),
        ({"overrides": {"tune": 5}}, "tune"),
        ({"overrides": {"holdout_periods": 99}}, "holdout_periods"),
        ({"overrides": {"learning_rate": 0.1}}, "learning_rate"),
        ({"controls": []}, "controls_reason"),
    ],
)
def test_invalid_plans_are_rejected(changes, message):
    with pytest.raises((ValidationError, PlanError)) as excinfo:
        make_plan(**changes)
    assert message in str(excinfo.value)


def test_plan_accepts_empty_controls_only_with_a_reason():
    plan = make_plan(controls=[], controls_reason="Client confirmed no promotion or holiday data applies.")
    assert plan.controls == []


def test_approval_text_shows_controls_or_why_none():
    tool = StartMmmRunTool()
    with_controls = tool.approval_text({"kpi": "revenue", "channels": ["tv"], "controls": ["google_promotion", "meta_promotion"], "date_start": "2024-01-01", "date_end": "2024-12-31"})
    assert "controls google_promotion, meta_promotion" in with_controls
    without = tool.approval_text({"kpi": "revenue", "channels": ["tv"], "controls": [], "controls_reason": "No promo data", "date_start": "2024-01-01", "date_end": "2024-12-31"})
    assert "controls none (No promo data)" in without


def test_approval_text_shows_the_country_scope_for_every_source():
    tool = StartMmmRunTool()
    scoped_text = tool.approval_text(
        {
            "kpi": "revenue",
            "channels": ["tv"],
            "controls": ["price"],
            "sources": [
                {"table": "sales_daily", "date_column": "date", "metrics": {"revenue": "revenue"}, "filters": {"country": "DE"}},
                {"table": "google_ads", "date_column": "date", "metrics": {"search": "spend"}},
            ],
            "date_start": "2024-01-01",
            "date_end": "2024-12-31",
        }
    )
    assert "scope sales_daily (country=DE); google_ads (no filter)" in scoped_text


def test_start_mmm_run_asks_for_controls_or_a_reason():
    service = RecordingService()
    result = run_tool(StartMmmRunTool(), tool_args(controls=[]), service)
    assert result.startswith("Error:") and "controls_reason" in result
    assert service.plans == []


def test_build_config_applies_whitelisted_overrides_and_sorts_channels():
    plan = make_plan(channels=["tv", "search"], overrides={"adstock_l_max": 6, "chains": 2})
    config = build_config(plan)
    assert config["target_column"] == "revenue"
    assert config["channels"] == ["search", "tv"]
    assert config["model"]["adstock"]["l_max"] == 6
    assert config["sampling"]["chains"] == 2
    assert load_defaults()["model"]["adstock"]["l_max"] == 10
    assert "chains:" in dump_config(config)


def test_build_config_sets_holdout_periods_from_defaults_or_overrides():
    assert build_config(make_plan())["validation"] == {"holdout_periods": 8}
    assert build_config(make_plan(overrides={"holdout_periods": 0}))["validation"] == {"holdout_periods": 0}
    assert load_defaults()["validation"]["holdout_periods"] == 8


def test_render_script_is_safe_for_hostile_rationale():
    rationale = 'Triple """ quote, a backslash \\ and a {{CONFIG_LITERAL}} token'
    plan = make_plan(rationale=rationale)
    config = build_config(plan)
    script = render_script(config, plan.to_dict(), "2024-06-01T00:00:00+00:00")
    tree = ast.parse(script)
    assigned = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                assigned[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    assert assigned["CONFIG"] == config
    assert assigned["PLAN_SUMMARY"]["rationale"] == rationale
    assert assigned["GENERATED_AT"] == "2024-06-01T00:00:00+00:00"


class FakeCatalog:
    def __init__(self, columns: dict[str, list[dict[str, str]]], metric_rows: dict[str, list[dict]]):
        self.columns = columns
        self.metric_rows = metric_rows
        self.calls: list[tuple] = []

    async def get_connector_columns(self, pool, schema, table):
        return self.columns.get(table)

    async def get_daily_metric_rows(self, pool, schema, table, org_id, date_column, metric_columns, start, end, filters=None):
        self.calls.append((table, org_id, date_column, tuple(metric_columns), start, end, filters))
        return self.metric_rows.get(table, [])


def column(name: str, data_type: str = "numeric") -> dict[str, str]:
    return {"name": name, "data_type": data_type}


def good_columns() -> dict[str, list[dict[str, str]]]:
    shared = [column("org_id", "text"), column("date", "date"), column("revenue"), column("tv_spend"), column("avg_price")]
    return {
        "sales_daily": shared,
        "google_ads": [column("org_id", "text"), column("date", "date"), column("search_spend")],
    }


def day_rows(count: int, value: float = 1.0, width: int = 3) -> list[dict]:
    return [{"date": START + timedelta(days=i), "values": [value] * width} for i in range(count)]


def test_validate_sources_accepts_org_scoped_tables(monkeypatch):
    fake = FakeCatalog(good_columns(), {})
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    asyncio.run(validate_sources(None, "datasets", make_plan()))


def test_validate_sources_refuses_shared_tables(monkeypatch):
    columns = good_columns()
    columns["sales_daily"] = [column("date", "date"), column("revenue"), column("tv_spend"), column("avg_price")]
    fake = FakeCatalog(columns, {})
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    with pytest.raises(PlanError, match="shared across orgs"):
        asyncio.run(validate_sources(None, "datasets", make_plan()))


def test_validate_sources_refuses_missing_and_non_numeric_columns(monkeypatch):
    columns = good_columns()
    columns["google_ads"] = [column("org_id", "text"), column("date", "date"), column("search_spend", "text")]
    fake = FakeCatalog(columns, {})
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    with pytest.raises(PlanError, match="not numeric"):
        asyncio.run(validate_sources(None, "datasets", make_plan()))


def test_build_dataset_joins_sources_by_date_and_zero_fills(monkeypatch):
    metric_rows = {
        "sales_daily": day_rows(30, value=5.0),
        "google_ads": [{"date": START + timedelta(days=i), "values": [2.0]} for i in range(0, 30, 2)],

    }
    fake = FakeCatalog(good_columns(), metric_rows)
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    monkeypatch.setattr(catalog, "get_daily_metric_rows", fake.get_daily_metric_rows)
    result = asyncio.run(build_dataset(None, "datasets", ORG_A, make_plan()))
    assert result.columns == ["date", "revenue", "tv", "price", "search"]
    assert len(result.rows) == 30
    assert result.rows[1]["search"] == 0.0
    assert result.rows[0]["search"] == 2.0
    assert {call[1] for call in fake.calls} == {ORG_A}


def test_build_dataset_enforces_minimum_usable_rows(monkeypatch):
    metric_rows = {"sales_daily": day_rows(MIN_ROWS - 1), "google_ads": day_rows(60, width=1)}
    fake = FakeCatalog(good_columns(), metric_rows)
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    monkeypatch.setattr(catalog, "get_daily_metric_rows", fake.get_daily_metric_rows)
    with pytest.raises(PlanError, match="usable rows"):
        asyncio.run(build_dataset(None, "datasets", ORG_A, make_plan()))


def scoped_plan(country: str = "DE") -> MMMPlan:
    sources = [
        SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}, filters={"country": country}),
        SourceSpec(table="google_ads", date_column="date", metrics={"search": "search_spend"}, filters={"country": country}),
    ]
    return make_plan(sources=sources)


def test_source_filters_reject_bad_identifiers_and_values():
    with pytest.raises(ValidationError, match="not a valid connector table or column name"):
        SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue"}, filters={"country; drop": "DE"})
    with pytest.raises(ValidationError, match="must be 1 to 100 characters"):
        SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue"}, filters={"country": "  "})
    with pytest.raises(ValidationError, match="must be 1 to 100 characters"):
        SourceSpec(table="sales_daily", date_column="date", metrics={"revenue": "revenue"}, filters={"country": "x" * 101})


def scoped_columns() -> dict[str, list[dict[str, str]]]:
    columns = good_columns()
    columns["sales_daily"] = columns["sales_daily"] + [column("country", "text")]
    columns["google_ads"] = columns["google_ads"] + [column("country", "text")]
    return columns


def test_validate_sources_refuses_missing_or_non_text_filter_columns(monkeypatch):
    columns = scoped_columns()
    columns["google_ads"] = [column("org_id", "text"), column("date", "date"), column("search_spend")]
    fake = FakeCatalog(columns, {})
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    with pytest.raises(PlanError, match="filter column 'country' not found"):
        asyncio.run(validate_sources(None, "datasets", scoped_plan()))
    columns["google_ads"] = [column("org_id", "text"), column("date", "date"), column("search_spend"), column("country", "integer")]
    with pytest.raises(PlanError, match="not text"):
        asyncio.run(validate_sources(None, "datasets", scoped_plan()))


def test_build_dataset_passes_source_filters_to_the_query(monkeypatch):
    metric_rows = {"sales_daily": day_rows(30), "google_ads": day_rows(30, width=1)}
    fake = FakeCatalog(scoped_columns(), metric_rows)
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    monkeypatch.setattr(catalog, "get_daily_metric_rows", fake.get_daily_metric_rows)
    asyncio.run(build_dataset(None, "datasets", ORG_A, scoped_plan("DE")))
    assert [call[6] for call in fake.calls] == [{"country": "DE"}, {"country": "DE"}]


def test_build_dataset_passes_no_filters_when_unscoped(monkeypatch):
    metric_rows = {"sales_daily": day_rows(30), "google_ads": day_rows(30, width=1)}
    fake = FakeCatalog(good_columns(), metric_rows)
    monkeypatch.setattr(catalog, "get_connector_columns", fake.get_connector_columns)
    monkeypatch.setattr(catalog, "get_daily_metric_rows", fake.get_daily_metric_rows)
    asyncio.run(build_dataset(None, "datasets", ORG_A, make_plan()))
    assert [call[6] for call in fake.calls] == [None, None]


def test_build_config_records_data_scope_only_when_filtered():
    scoped_config = build_config(scoped_plan("DE"))
    assert scoped_config["data_scope"] == [
        {"table": "sales_daily", "filters": {"country": "DE"}},
        {"table": "google_ads", "filters": {"country": "DE"}},
    ]
    assert "data_scope" not in build_config(make_plan())


def test_run_folder_reports_every_missing_file(tmp_path):
    assert missing_outputs(tmp_path) == list(RUN_FILES)
    write_inputs(tmp_path, ["date", "revenue"], [{"date": "2024-01-01", "revenue": 1.0}], "a: 1\n", "print(1)\n")
    assert missing_outputs(tmp_path) == ["evaluation.json", "mmm_model.nc"]
    (tmp_path / "evaluation.json").write_text("{}", encoding="utf-8")
    (tmp_path / "mmm_model.nc").write_bytes(b"")
    assert missing_outputs(tmp_path) == ["mmm_model.nc"]
    (tmp_path / "mmm_model.nc").write_bytes(b"model")
    assert missing_outputs(tmp_path) == []


def test_sandbox_env_drops_secrets():
    env = sandbox_env({"PATH": "/bin", "HOME": "/h", "AZURE_CLIENT_SECRET": "x", "MONGO_URI": "y"})
    assert env["PATH"] == "/bin"
    assert "AZURE_CLIENT_SECRET" not in env and "MONGO_URI" not in env
    assert env["PYTHONUNBUFFERED"] == "1"


def test_run_script_streams_progress_and_returns_result(tmp_path):
    code = (
        'import json\n'
        'print("@@progress " + json.dumps({"stage": "sampling", "percent": 50, "message": "m"}), flush=True)\n'
        'print("@@result " + json.dumps({"status": "success"}), flush=True)\n'
    )
    seen: list[dict] = []

    async def on_progress(payload):
        seen.append(payload)

    outcome = asyncio.run(run_script([sys.executable, "-c", code], tmp_path, on_progress, env=sandbox_env()))
    assert outcome.code == 0
    assert outcome.result == {"status": "success"}
    assert seen == [{"stage": "sampling", "percent": 50, "message": "m"}]


def test_run_script_reports_nonzero_exit_with_stderr_tail(tmp_path):
    code = 'import sys\nprint("boom", file=sys.stderr)\nsys.exit(3)\n'

    async def on_progress(payload):
        pass

    outcome = asyncio.run(run_script([sys.executable, "-c", code], tmp_path, on_progress, env=sandbox_env()))
    assert outcome.code == 3
    assert outcome.result is None
    assert outcome.tail == ["boom"]


def test_run_script_times_out_and_kills_the_process(tmp_path):
    async def on_progress(payload):
        pass

    with pytest.raises(SandboxError, match="exceeded"):
        asyncio.run(
            run_script([sys.executable, "-c", "import time\ntime.sleep(30)"], tmp_path, on_progress, env=sandbox_env(), timeout_s=0.5)
        )


class RecordingService:
    def __init__(self):
        self.plans: list[MMMPlan] = []

    async def submit_mmm_plan(self, *, org_id, user_id, chat_id, plan):
        self.plans.append(plan)
        return "job-123"


def run_tool(tool, args: dict, service) -> str:
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id="user-1", chat_id="chat-1"))
    try:
        return asyncio.run(tool.ainvoke(args))
    finally:
        bind_scope(None)


def tool_args(**changes) -> dict:
    args = {
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": [
            {"table": "sales_daily", "date_column": "date", "metrics": {"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}},
            {"table": "google_ads", "date_column": "date", "metrics": {"search": "search_spend"}},
        ],
        "date_start": "2024-01-01",
        "date_end": "2024-12-31",
        "overrides": {"adstock_l_max": 8},
        "rationale": "Revenue with TV and search spend.",
    }
    args.update(changes)
    return args


def test_start_mmm_run_submits_a_valid_plan():
    service = RecordingService()
    result = run_tool(StartMmmRunTool(), tool_args(), service)
    assert "job-123" in result
    assert service.plans[0].kpi == "revenue"
    assert service.plans[0].overrides == {"adstock_l_max": 8}


def test_start_mmm_run_returns_plan_errors_to_the_agent():
    service = RecordingService()
    result = run_tool(StartMmmRunTool(), tool_args(kpi="sales"), service)
    assert result.startswith("Error:") and "not a mapped output" in result
    assert service.plans == []


def test_start_mmm_run_rejects_unsafe_identifiers_cleanly():
    service = RecordingService()
    args = tool_args()
    args["sources"][0]["table"] = "Sales-Daily; DROP"
    result = run_tool(StartMmmRunTool(), args, service)
    assert result.startswith("Error:") and "not a valid connector table" in result
    assert service.plans == []


def test_start_mmm_run_is_registered_and_needs_approval():
    tool = next(t for t in STATIC_TOOLS if t.name == START_MMM_RUN_TOOL)
    assert tool.allowed_decisions == ["approve", "edit", "reject"]


SMOKE = os.environ.get("RUN_MMM_SMOKE") == "1"


@pytest.mark.skipif(not SMOKE, reason="slow pymc run; set RUN_MMM_SMOKE=1 to execute")
def test_generated_script_trains_and_fills_the_run_folder(tmp_path: Path):
    import numpy as np

    rng = np.random.default_rng(0)
    weeks = 60
    tv = rng.uniform(1_000, 5_000, weeks)
    search = rng.uniform(500, 2_000, weeks)
    price = rng.uniform(9, 11, weeks)
    revenue = 3 * tv + 5 * search - 200 * price + 20_000 + rng.normal(0, 500, weeks)
    rows = [
        {"date": (START + timedelta(weeks=i)).isoformat(), "revenue": float(revenue[i]), "tv": float(tv[i]),
         "search": float(search[i]), "price": float(price[i])}
        for i in range(weeks)
    ]
    plan = make_plan(sources=[SourceSpec(table="t", date_column="date", metrics={"revenue": "r", "tv": "t", "price": "p", "search": "s"})])
    config = build_config(plan)
    config["sampling"].update({"chains": 1, "tune": 10, "draws": 10})
    script = render_script(config, plan.to_dict(), "2024-06-01T00:00:00+00:00")
    write_inputs(tmp_path, ["date", "revenue", "tv", "price", "search"], rows, dump_config(config), script)

    async def on_progress(payload):
        pass

    outcome = asyncio.run(run_script([sys.executable, str(tmp_path / "train.py")], tmp_path, on_progress, env=sandbox_env()))
    assert outcome.code == 0, outcome.tail
    assert outcome.result and outcome.result["status"] == "success"
    assert missing_outputs(tmp_path) == []

    evaluation = json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["metric_errors"] == {}, evaluation["metric_errors"]
    fit_keys = {"r2", "mae", "rmse", "bias", "mape_pct", "wmape_pct", "hdi94_coverage_pct", "hdi50_coverage_pct",
                "durbin_watson", "shapiro_wilk_p", "residual_trend_p", "breusch_pagan_p", "worst_residuals"}
    assert fit_keys <= evaluation["fit"].keys()
    assert set(evaluation["channels"]) == set(evaluation["contributions"]["channels"])
    for block in ("roas", "incremental_roas", "marginal_roas"):
        assert set(evaluation[block]) == {"all_time", "yearly", "monthly"}
        assert set(evaluation[block]["all_time"]) == set(evaluation["channels"])
    assert set(evaluation["transformations"]["saturation_lam"]) == set(evaluation["channels"])
    holdout_periods = 8
    assert evaluation["validation"]["holdout_periods"] == holdout_periods
    assert evaluation["validation"]["train_rows"] == weeks - holdout_periods
    assert evaluation["validation"]["holdout_rows"] == holdout_periods
    assert evaluation["rows"] == weeks - holdout_periods
    assert evaluation["validation"]["holdout_start"] < evaluation["validation"]["holdout_end"]
    assert evaluation["validation"]["train_end"] < evaluation["validation"]["holdout_start"]
    assert fit_keys <= evaluation["fit"].keys()
    assert evaluation["fit"]["observations"] == weeks - holdout_periods
    assert fit_keys <= evaluation["holdout"].keys()
    assert evaluation["holdout"]["observations"] == holdout_periods

