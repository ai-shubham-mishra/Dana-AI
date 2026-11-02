import asyncio

import pytest

from agent.tools.ml_ops.ml.model_versions.list_model_versions import ListModelVersionsTool
from agent.tools.ml_ops.ml.model_versions.retrain_model_version import RetrainModelVersionTool
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


def test_retrain_queues_a_job_for_the_chosen_version():
    calls = []

    async def retrain(model_id, version):
        calls.append((model_id, version))
        return "job-42"

    out = run(RetrainModelVersionTool(), {"model_id": "m1", "version": 2}, FakeService(FakeRegistry(), retrain))
    assert calls == [("m1", 2)]
    assert "job job-42" in out


def test_retrain_reports_an_unknown_version_without_running():
    async def retrain(model_id, version):
        raise LookupError(f"model {model_id} has no version {version}")

    out = run(RetrainModelVersionTool(), {"model_id": "m1", "version": 9}, FakeService(FakeRegistry(), retrain))
    assert "has no version 9" in out
    assert "list_model_versions" in out


def test_retrain_reports_an_invalid_stored_configuration():
    async def retrain(model_id, version):
        raise PlanError("kpi missing")

    out = run(RetrainModelVersionTool(), {"model_id": "m1", "version": 2}, FakeService(FakeRegistry(), retrain))
    assert "cannot be retrained" in out


def test_retrain_requires_a_human_decision_and_is_registered():
    tool = RetrainModelVersionTool()
    assert tool.allowed_decisions == ["approve", "edit", "reject"]
    assert "retrain_model_version" in interrupt_policy(STATIC_TOOLS)
    assert "list_model_versions" in {t.name for t in STATIC_TOOLS}
    assert tool.approval_text({"model_id": "m1", "version": 2}).endswith(
        "Retrain model m1 using the saved configuration of version 2?"
    )


@pytest.mark.parametrize(
    ("tool", "args"),
    [(ListModelVersionsTool(), {"model_id": "m1"}), (RetrainModelVersionTool(), {"model_id": "m1", "version": 1})],
)
def test_tools_are_unavailable_without_a_scope(tool, args):
    bind_scope(None)
    assert "unavailable" in asyncio.run(tool.ainvoke(args))
