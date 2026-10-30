import asyncio
from datetime import date

from agent.tools.system_ops.connectors.list_connector_column_values import ListConnectorColumnValuesTool
from integrations.connectors import catalog
from integrations.training.scope import JobScope, bind_scope
from tests.test_connectors import FakeDB, FakePool

ORG_A = "org-a"
COLUMNS = [
    {"name": "org_id", "data_type": "text"},
    {"name": "date", "data_type": "date"},
    {"name": "country", "data_type": "text"},
    {"name": "spend", "data_type": "double precision"},
]


def scoped() -> None:
    bind_scope(JobScope(service=None, org_id=ORG_A, user_id="user-1", chat_id="chat-1"))


def tool() -> ListConnectorColumnValuesTool:
    return ListConnectorColumnValuesTool(pool=FakePool(FakeDB({})), datasets_schema="datasets")


def run_tool(args: dict) -> str:
    scoped()
    try:
        return asyncio.run(tool().ainvoke(args))
    finally:
        bind_scope(None)


def patch_catalog(monkeypatch, columns=COLUMNS, rows=None, seen=None):
    async def get_connector_columns(pool, schema, table):
        return columns if table == "google_ads" else None

    async def get_column_values(pool, schema, table, org_id, column, date_column, limit):
        if seen is not None:
            seen.append((table, org_id, column, date_column, limit))
        return rows or []

    async def list_connectors(pool, schema):
        return [{"name": "google_ads"}]

    monkeypatch.setattr(catalog, "get_connector_columns", get_connector_columns)
    monkeypatch.setattr(catalog, "get_column_values", get_column_values)
    monkeypatch.setattr(catalog, "list_connectors", list_connectors)


def value_row(value: str, rows: int) -> dict:
    return {"value": value, "row_count": rows, "first_date": date(2024, 1, 1), "last_date": date(2024, 12, 31)}


def test_lists_stored_values_with_counts_and_coverage(monkeypatch):
    seen = []
    patch_catalog(monkeypatch, rows=[value_row("DE", 365), value_row("FR", 300)], seen=seen)
    scoped()
    output = run_tool({"connector": "google_ads", "column": "country", "date_column": "date"})
    assert "2 values stored in 'google_ads.country':" in output
    assert "- 'DE': 365 rows, 2024-01-01 to 2024-12-31" in output
    assert seen == [("google_ads", ORG_A, "country", "date", 51)]


def test_marks_the_list_as_top_values_when_truncated(monkeypatch):
    rows = [value_row(f"C{i}", 10) for i in range(51)]
    patch_catalog(monkeypatch, rows=rows)
    scoped()
    output = run_tool({"connector": "google_ads", "column": "country", "date_column": "date"})
    assert "Top 50 values (more exist) stored in 'google_ads.country':" in output
    assert output.count("- 'C") == 50


def test_reports_when_the_column_has_no_values(monkeypatch):
    patch_catalog(monkeypatch, rows=[])
    scoped()
    output = run_tool({"connector": "google_ads", "column": "country", "date_column": "date"})
    assert "No values are stored in 'country' for this org" in output


def test_refuses_missing_or_non_text_columns(monkeypatch):
    patch_catalog(monkeypatch)
    scoped()
    missing = run_tool({"connector": "google_ads", "column": "region", "date_column": "date"})
    assert "'region' is not a text column in 'google_ads'" in missing
    numeric = run_tool({"connector": "google_ads", "column": "spend", "date_column": "date"})
    assert "'spend' is not a text column in 'google_ads'" in numeric
    bad_date = run_tool({"connector": "google_ads", "column": "country", "date_column": "country"})
    assert "'country' is not a date column in 'google_ads'" in bad_date


def test_refuses_shared_and_unknown_connectors(monkeypatch):
    patch_catalog(monkeypatch, columns=[c for c in COLUMNS if c["name"] != "org_id"])
    scoped()
    shared = run_tool({"connector": "google_ads", "column": "country", "date_column": "date"})
    assert "shared across orgs" in shared
    unknown = run_tool({"connector": "meta_ads", "column": "country", "date_column": "date"})
    assert "Connector 'meta_ads' does not exist" in unknown
    assert "google_ads" in unknown


def test_is_read_only_and_registered_without_approval():
    from agent.tools.registry import build_tools, interrupt_policy

    tools = build_tools(connector_pool=None)
    assert "list_connector_column_values" in {t.name for t in tools}
    assert "list_connector_column_values" not in interrupt_policy(tools)
