import asyncio
from datetime import date

from agent.tools.ml_ops.ml.data_prep.list_channels import ListChannelsTool
from agent.tools.registry import build_tools, interrupt_policy
from agent.tools.system_ops.connectors.list_channels_within_connector import ListChannelsWithinConnectorTool
from agent.tools.system_ops.connectors.list_connectors import ListConnectorsTool
from integrations.connectors.channels import derive_channels
from integrations.training.scope import JobScope, bind_scope
from tests.test_api import ORG_A, ORG_B
from tests.test_connectors import FakeDB, FakePool

ORG_C = "org-c"


def connector_pool() -> FakePool:
    return FakePool(
        FakeDB(
            {
                "sheet_ads": {
                    "estimate": 2,
                    "columns": [
                        ("org_id", "text"),
                        ("row_index", "integer"),
                        ("GAds-PMax_spend", "text"),
                        ("GAds-PMax_clicks", "text"),
                        ("Ad_Depth_Home", "text"),
                    ],
                    "rows": [
                        {"org_id": ORG_A, "GAds-PMax_spend": "10"},
                        {"org_id": ORG_A, "GAds-PMax_spend": "12"},
                        {"org_id": ORG_B, "GAds-PMax_spend": "99"},
                    ],
                },
                "sheet_tv": {
                    "estimate": -1,
                    "columns": [("TV_GRP", "double precision"), ("week", "date")],
                    "rows": [{"TV_GRP": 1.0, "week": date(2024, 1, 1)}],
                },
            }
        )
    )


def scoped(org_id: str = ORG_A) -> None:
    bind_scope(JobScope(service=None, org_id=org_id, user_id="user-1", chat_id="chat-1"))


def run_tool(tool, args: dict) -> str:
    try:
        return asyncio.run(tool.ainvoke(args))
    finally:
        bind_scope(None)


def test_derive_channels_keeps_only_metric_columns():
    channels = derive_channels(["GAds-PMax_spend", "GAds-PMax_clicks", "TV_GRP", "Ad_Depth_Home", "YT_Avg. Freq."])
    assert [(c["name"], c["metrics"]) for c in channels] == [
        ("GAds-PMax", ["spend", "clicks"]),
        ("TV", ["GRP"]),
    ]


def test_list_connectors_reports_channels_rows_and_scope():
    scoped()
    tool = ListConnectorsTool(pool=connector_pool(), datasets_schema="datasets")
    output = run_tool(tool, {})
    assert "Connectors (2):" in output
    assert "- sheet_ads: 1 channel, about 2 rows, org-scoped" in output
    assert "- sheet_tv: 1 channel, row count not analyzed yet, shared, no org_id column" in output


def test_list_channels_counts_rows_for_the_signed_in_org():
    scoped(ORG_A)
    tool = ListChannelsTool(pool=connector_pool(), datasets_schema="datasets")
    output = run_tool(tool, {"connector": "sheet_ads"})
    assert "Connector sheet_ads has 2 rows for this organization." in output
    assert "- GAds-PMax: spend, clicks" in output


def test_list_channels_warns_when_the_org_has_no_rows():
    scoped(ORG_C)
    tool = ListChannelsWithinConnectorTool(pool=connector_pool(), datasets_schema="datasets")
    output = run_tool(tool, {"connector": "sheet_ads"})
    assert "has 0 rows for this organization" in output
    assert "cannot be modelled from it" in output


def test_shared_table_is_labelled_as_shared():
    scoped()
    tool = ListChannelsTool(pool=connector_pool(), datasets_schema="datasets")
    output = run_tool(tool, {"connector": "sheet_tv"})
    assert "is a shared table with no org_id column" in output
    assert "- TV: GRP" in output


def test_unknown_connector_lists_available_connectors():
    scoped()
    tool = ListChannelsTool(pool=connector_pool(), datasets_schema="datasets")
    output = run_tool(tool, {"connector": "sheet_missing"})
    assert "Error:" in output
    assert "'sheet_missing' does not exist" in output
    assert "sheet_ads, sheet_tv" in output


def test_connector_tools_need_a_signed_in_scope():
    bind_scope(None)
    tool = ListConnectorsTool(pool=connector_pool(), datasets_schema="datasets")
    assert "no organization could be identified" in run_tool(tool, {})


def test_connector_tools_report_a_missing_pool():
    scoped()
    tool = ListConnectorsTool(pool=None, datasets_schema="datasets")
    assert "connector database is not configured" in run_tool(tool, {})


def test_only_channel_selection_needs_approval():
    tools = build_tools(connector_pool=connector_pool(), datasets_schema="datasets")
    policy = interrupt_policy(tools)
    assert policy["list_channels_within_connector"] == {"allowed_decisions": ["approve", "edit", "reject"]}
    assert "list_connectors" not in policy
    assert "list_channels" not in policy


def test_build_tools_passes_the_pool_to_every_connector_tool():
    pool = connector_pool()
    tools = {tool.name: tool for tool in build_tools(connector_pool=pool, datasets_schema="analytics")}
    for name in ("list_connectors", "list_channels_within_connector", "list_channels"):
        assert tools[name].pool is pool
        assert tools[name].datasets_schema == "analytics"


def test_build_tools_without_a_pool_still_registers_connector_tools():
    tools = {tool.name: tool for tool in build_tools()}
    assert tools["list_connectors"].pool is None
    assert tools["list_connectors"].datasets_schema == "datasets"
