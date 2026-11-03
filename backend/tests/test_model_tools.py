import asyncio
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.runtime import approval_payload
from agent.tools.ml_ops.ml.model_versions.list_model_versions import ListModelVersionsTool
from agent.tools.ml_ops.ml.model_versions.retrain_model_version import RETRAIN_DECISIONS, RetrainModelVersionTool
from agent.tools.registry import STATIC_TOOLS, interrupt_policy
from integrations.training.mmm.plan import PlanError
from integrations.training.scope import JobScope, bind_scope

ORG_A = "org-a"
USER_1 = "user-1"

VERSION = {
    "version": 2,
    "source": "retrain",
    "created_at": "2026-11-01",
    "created_by_email": "a@b.c",
    "job_id": "job-9",
    "params": {
        "kpi": "sales",
        "channels": ["google_ads", "meta"],
        "controls": ["price"],
        "sources": [
            {
                "table": "marketing_daily",
                "date_column": "date",
                "metrics": {"sales": "sales", "google_ads": "google_ads_spend", "meta": "meta_spend", "price": "avg_price"},
            }
        ],
        "date_start": "2025-01-01",
        "date_end": "2025-12-31",
    },
}


class FakeRegistry:
    def __init__(self, versions=None):
        self.versions = versions or []

    async def list_models(self, *, org_id, user_id, limit=50):
        return [{"id": "m1", "name": "MMM · sales", "latest_version": 2, "version_count": 2}] if self.versions else []

    async def list_versions(self, *, org_id, user_id, model_id):
        return self.versions if model_id == "m1" else []

    async def get_model(self, *, org_id, user_id, model_id):
        return {"id": "m1", "name": "MMM · sales"} if self.versions and model_id == "m1" else None

    async def get_version(self, *, org_id, user_id, model_id, version):
        if model_id != "m1":
            return None
        return next((v for v in self.versions if v["version"] == version), None)


class FakeService:
    def __init__(self, registry, retrain=None):
        self.models = registry
        self._retrain = retrain

    async def retrain_version(self, *, org_id, user_id, chat_id, model_id, version, actor_email=None):
        if self._retrain is None:
            raise AssertionError("retrain should not be called")
        return await self._retrain(model_id=model_id, version=version)


def run(tool, args, service):
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1"))
    try:
        return asyncio.run(tool.ainvoke(args))
    finally:
        bind_scope(None)


def test_lists_models_when_no_model_is_given():
    out = run(ListModelVersionsTool(), {}, FakeService(FakeRegistry(versions=[VERSION])))
    assert "- m1: MMM · sales (latest version 2, 2 version(s))" in out


def test_shows_the_saved_configuration_of_each_version():
    out = run(ListModelVersionsTool(), {"model_id": "m1"}, FakeService(FakeRegistry(versions=[VERSION])))
    assert "Version 2 (retrain" in out
    assert "KPI: sales" in out
    assert "Channels: google_ads, meta" in out
    assert "Controls: price" in out
    assert "Period: 2025-01-01 to 2025-12-31" in out


def test_unknown_model_is_reported_as_an_error():
    bind_scope(JobScope(service=FakeService(FakeRegistry()), org_id=ORG_A, user_id=USER_1, chat_id="c"))
    try:
        out = asyncio.run(ListModelVersionsTool().ainvoke({"model_id": "missing"}))
    finally:
        bind_scope(None)
    assert "No model with id missing" in out


class RetrainState(TypedDict):
    out: str


def _retrain_graph(args):
    tool = RetrainModelVersionTool()

    async def retrain_node(state: RetrainState) -> dict:
        return {"out": await tool.ainvoke(args)}

    builder = StateGraph(RetrainState)
    builder.add_node("retrain", retrain_node)
    builder.add_edge(START, "retrain")
    builder.add_edge("retrain", END)
    return builder.compile(checkpointer=MemorySaver())


async def _retrain_turn(service, args, decision=None):
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1"))
    try:
        graph = _retrain_graph(args)
        config = {"configurable": {"thread_id": "thread-1"}}
        await graph.ainvoke({"out": ""}, config)
        snapshot = await graph.aget_state(config)
        if not snapshot.interrupts or decision is None:
            return snapshot.values["out"], snapshot.interrupts
        final = await graph.ainvoke(Command(resume={"decisions": [decision]}), config)
        return final["out"], snapshot.interrupts
    finally:
        bind_scope(None)


def retrain_turn(service, args, decision=None):
    return asyncio.run(_retrain_turn(service, args, decision))


def test_retrain_is_not_gated_by_the_middleware_so_the_card_can_show_the_config():
    assert "retrain_model_version" not in interrupt_policy(STATIC_TOOLS)
    assert "list_model_versions" in {t.name for t in STATIC_TOOLS}
    assert RETRAIN_DECISIONS == ["approve", "reject"]


def test_approval_card_carries_the_saved_configuration():
    out, interrupts = retrain_turn(FakeService(FakeRegistry([VERSION])), {"model_id": "m1", "version": 2})
    assert out == ""
    assert len(interrupts) == 1
    action = approval_payload(interrupts[0])["actions"][0]
    assert action["name"] == "retrain_model_version"
    assert action["allowed_decisions"] == ["approve", "reject"]
    assert action["args"] == {"model": "MMM · sales", "from_version": 2, "configuration": VERSION["params"]}
    assert "version 2" in action["description"]


def test_approving_queues_a_job_for_the_chosen_version():
    calls = []

    async def retrain(model_id, version):
        calls.append((model_id, version))
        return "job-42"

    service = FakeService(FakeRegistry([VERSION]), retrain)
    out, _ = retrain_turn(service, {"model_id": "m1", "version": 2}, {"type": "approve"})
    assert calls == [("m1", 2)]
    assert "job job-42" in out


def test_rejecting_starts_no_run_and_keeps_the_reason():
    out, _ = retrain_turn(
        FakeService(FakeRegistry([VERSION])),
        {"model_id": "m1", "version": 2},
        {"type": "reject", "message": "too expensive"},
    )
    assert "no run was started" in out
    assert "too expensive" in out


def test_retrain_reports_an_unknown_version_without_asking_for_approval():
    out, interrupts = retrain_turn(FakeService(FakeRegistry([VERSION])), {"model_id": "m1", "version": 9})
    assert "has no version 9" in out
    assert "list_model_versions" in out
    assert not interrupts


def test_retrain_reports_an_invalid_stored_configuration_without_asking_for_approval():
    broken = {**VERSION, "params": {"kpi": "sales"}}
    out, interrupts = retrain_turn(FakeService(FakeRegistry([broken])), {"model_id": "m1", "version": 2})
    assert "cannot be retrained" in out
    assert not interrupts


def test_service_side_plan_error_is_reported_after_approval():
    async def retrain(model_id, version):
        raise PlanError("kpi missing")

    service = FakeService(FakeRegistry([VERSION]), retrain)
    out, _ = retrain_turn(service, {"model_id": "m1", "version": 2}, {"type": "approve"})
    assert "cannot be retrained" in out


def test_retrain_is_registered_and_list_tool_is_available():
    assert "list_model_versions" in {t.name for t in STATIC_TOOLS}
    assert RetrainModelVersionTool().name in {t.name for t in STATIC_TOOLS}


@pytest.mark.parametrize(
    ("tool", "args"),
    [(ListModelVersionsTool(), {"model_id": "m1"}), (RetrainModelVersionTool(), {"model_id": "m1", "version": 1})],
)
def test_tools_are_unavailable_without_a_scope(tool, args):
    bind_scope(None)
    assert "unavailable" in asyncio.run(tool.ainvoke(args))
