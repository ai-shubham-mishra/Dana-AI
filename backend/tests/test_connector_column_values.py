import asyncio
from datetime import date

from agent.tools.system_ops.connectors.find_connector_columns import FindConnectorColumnsTool
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
    assert seen == [("google_ads", ORG_A, "country", {"name": "date", "data_type": "date"}, 51)]


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


def test_accepts_text_date_columns_like_week(monkeypatch):
    seen = []
    columns = [*COLUMNS, {"name": "week", "data_type": "text"}]
    patch_catalog(monkeypatch, columns=columns, rows=[value_row("CH", 250)], seen=seen)
    scoped()
    output = run_tool({"connector": "google_ads", "column": "country", "date_column": "week"})
    assert "stored in 'google_ads.country':" in output
    assert "- 'CH': 250 rows" in output
    assert seen == [("google_ads", ORG_A, "country", {"name": "week", "data_type": "text"}, 51)]


class CapturingDB(FakeDB):
    def answer(self, text, params):
        self.queries.append((text, params))
        return []


def test_text_date_column_is_cast_by_iso_prefix_before_grouping():
    db = CapturingDB({})
    asyncio.run(
        catalog.get_column_values(
            FakePool(db), "datasets", "sheet_x", ORG_A, "country", {"name": "week", "data_type": "text"}, 5
        )
    )
    text, params = db.queries[-1]
    assert "substring(" in text and "AS _rows" in text and "GROUP BY 1" in text
    assert params == (catalog.ISO_DATE_PREFIX, ORG_A, 5)


def test_native_date_column_needs_no_text_cast_param():
    db = CapturingDB({})
    asyncio.run(
        catalog.get_column_values(FakePool(db), "datasets", "sheet_x", ORG_A, "country", {"name": "date", "data_type": "date"}, 5)
    )
    _, params = db.queries[-1]
    assert params == (ORG_A, 5)


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
    assert "find_connector_columns" in {t.name for t in tools}
    assert "find_connector_columns" not in interrupt_policy(tools)


FUZZY_COLUMNS = [
    {"name": "org_id", "data_type": "text"},
    {"name": "date", "data_type": "date"},
    {"name": "GAds-Demand-Gen_spend", "data_type": "double precision"},
    {"name": "meta_spend", "data_type": "double precision"},
]


def find_tool() -> FindConnectorColumnsTool:
    return FindConnectorColumnsTool(pool=FakePool(FakeDB({})), datasets_schema="datasets")


def run_find(args: dict) -> str:
    scoped()
    try:
        return asyncio.run(find_tool().ainvoke(args))
    finally:
        bind_scope(None)


def test_finds_hyphenated_columns_with_a_fuzzy_pattern(monkeypatch):
    patch_catalog(monkeypatch, columns=FUZZY_COLUMNS)
    output = run_find({"connector": "google_ads", "pattern": "gads.*demand"})
    assert "1 column(s) in 'google_ads' match 'gads.*demand':" in output
    assert "- 'GAds-Demand-Gen_spend' (double precision)" in output
    assert "meta_spend" not in output


def test_pattern_is_case_insensitive_and_can_match_alternatives(monkeypatch):
    patch_catalog(monkeypatch, columns=FUZZY_COLUMNS)
    output = run_find({"connector": "google_ads", "pattern": "SPEND|demand"})
    assert "2 column(s)" in output
    assert "GAds-Demand-Gen_spend" in output and "meta_spend" in output


def test_no_match_lists_the_available_columns(monkeypatch):
    patch_catalog(monkeypatch, columns=FUZZY_COLUMNS)
    output = run_find({"connector": "google_ads", "pattern": "impressions"})
    assert "No columns in 'google_ads' match 'impressions'" in output
    assert "Its columns are: org_id, date, GAds-Demand-Gen_spend, meta_spend." in output


def test_refuses_invalid_patterns_and_unknown_connectors(monkeypatch):
    patch_catalog(monkeypatch, columns=FUZZY_COLUMNS)
    bad = run_find({"connector": "google_ads", "pattern": "gads("})
    assert "not a valid regular expression" in bad
    empty = run_find({"connector": "google_ads", "pattern": "   "})
    assert "pattern must be 1 to 100 characters" in empty
    unknown = run_find({"connector": "meta_ads", "pattern": "spend"})
    assert "Connector 'meta_ads' does not exist" in unknown
