import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from agent.tools.ml_ops.ml.training.start_mmm_run import StartMmmRunTool
from integrations.model_registry.lifecycle import ModelLifecycle
from integrations.model_registry.registry import (
    InvalidModelName,
    InvalidTag,
    ModelNameTaken,
    ModelRegistry,
    normalize_model_name,
)
from integrations.training.scope import JobScope, bind_scope
from tests.test_api import ORG_A, USER_1, auth, member, mint, raw_db, settings, static_secret  # noqa: F401
from tests.test_deployments import HEADERS, _seed_sync, _wait_for_status, api, run_with_db  # noqa: F401
from tests.test_mmm_run import RecordingService, run_tool, tool_args


class FakeTraining:
    async def get_job(self, *, org_id, user_id, job_id):
        return None

    async def delete_jobs(self, *, org_id, user_id, job_ids, actor_email=None):
        return {"deleted": [], "skipped": [{"id": job_id, "reason": "Job not found"} for job_id in job_ids]}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Q1   Revenue  ", "Q1 Revenue"),
        ("Sales · Mix (EU)", "Sales · Mix (EU)"),
    ],
)
def test_model_names_are_trimmed_and_collapsed(raw, expected):
    assert normalize_model_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "x" * 81, "bad/name", "semi;colon"])
def test_invalid_model_names_are_rejected(raw):
    with pytest.raises(InvalidModelName):
        normalize_model_name(raw)


def test_names_are_unique_case_insensitively_and_suggestions_avoid_taken_names(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        assert await registry.name_taken(org_id=ORG_A, user_id=USER_1, name="mmm · SALES")
        assert not await registry.name_taken(org_id=ORG_A, user_id=USER_1, name="Brand new")
        suggestions = await registry.suggest_names(org_id=ORG_A, user_id=USER_1, base="MMM · sales")
        assert len(suggestions) == 3 and len(set(suggestions)) == 3
        assert all(name.startswith("MMM · sales-") for name in suggestions)
        for name in suggestions:
            assert not await registry.name_taken(org_id=ORG_A, user_id=USER_1, name=name)

    run_with_db(settings, body)


def test_purge_removes_archived_versions_once_due(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        await registry.archive_versions(
            org_id=ORG_A, user_id=USER_1, model_id="m1", versions=[1], actor_email="a@b.c"
        )
        assert await registry.due_purge() == []
        await db.model_versions.update_one({"model_id": "m1"}, {"$set": {"purge_at": datetime.now(UTC) - timedelta(seconds=1)}})
        assert await ModelLifecycle(registry=registry, training=FakeTraining(), deployments=None).purge_due() == 1
        assert await db.models.count_documents({"id": "m1"}) == 0
        assert await db.model_versions.count_documents({"model_id": "m1"}) == 0

    run_with_db(settings, body)


def test_start_mmm_run_reports_a_taken_name_with_suggestions():
    class TakenService(RecordingService):
        async def submit_mmm_plan(self, **kwargs):
            raise ModelNameTaken("Revenue Q1", ["Revenue Q1-a1b2c3"])

    result = run_tool(StartMmmRunTool(), tool_args(), TakenService())
    assert "already exists" in result
    assert "Revenue Q1-a1b2c3" in result


def test_delete_model_removes_it_when_nothing_is_deployed(api, raw_db):
    _seed_sync(raw_db)
    res = api.delete("/api/v1/models/m1", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["outcome"] == "deleted"
    assert api.get("/api/v1/models", headers=HEADERS).json() == []
    assert api.get("/api/v1/models/m1", headers=HEADERS).status_code == 404


def test_deployed_version_needs_confirmation_then_deallocates_and_archives(api, raw_db):
    _seed_sync(raw_db)
    dep_id = api.post("/api/v1/models/m1/versions/1/deployments", headers=HEADERS).json()["id"]
    _wait_for_status(api, dep_id, "running")

    blocked = api.delete("/api/v1/models/m1/versions/1", headers=HEADERS)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "needs_confirmation"
    assert blocked.json()["detail"]["deployments"][0]["id"] == dep_id

    archived = api.delete("/api/v1/models/m1/versions/1", params={"deallocate": True}, headers=HEADERS)
    assert archived.status_code == 200
    assert archived.json()["outcome"] == "archived"
    assert api.get(f"/api/v1/deployments/{dep_id}", headers=HEADERS).json()["status"] == "stopped"
    assert api.get("/api/v1/models", headers=HEADERS).json() == []
    assert raw_db.model_versions.find_one({"model_id": "m1"})["purge_at"] is not None


def test_version_whose_training_job_is_missing_is_still_deleted(api, raw_db):
    _seed_sync(raw_db)
    res = api.delete("/api/v1/models/m1/versions/1", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["outcome"] == "deleted"
    assert api.get("/api/v1/models/m1", headers=HEADERS).status_code == 404


def test_deleting_unknown_model_or_version_is_not_found(api, raw_db):
    _seed_sync(raw_db)
    assert api.delete("/api/v1/models/missing", headers=HEADERS).status_code == 404
    assert api.delete("/api/v1/models/m1/versions/9", headers=HEADERS).status_code == 404


def _record_second_version():
    return dict(
        org_id=ORG_A, user_id=USER_1, job_id="job-2", params={}, metrics=None, artifact=None,
        actor_email="b@c.d", name="MMM · sales", kpi="sales", model_id="m1",
    )


def test_latest_tag_follows_the_newest_version_and_can_be_moved(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        await registry.record_version(**_record_second_version())
        versions = {v["version"]: v for v in await registry.list_versions(org_id=ORG_A, user_id=USER_1, model_id="m1")}
        assert versions[2]["tags"] == ["latest"] and "latest" not in versions[1].get("tags", [])
        await registry.set_tag(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, tag="latest", actor_email="a@b.c")
        versions = {v["version"]: v for v in await registry.list_versions(org_id=ORG_A, user_id=USER_1, model_id="m1")}
        assert versions[1]["tags"] == ["latest"] and "latest" not in versions[2].get("tags", [])

    run_with_db(settings, body)


def test_set_tag_validates_tag_and_target_version(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        with pytest.raises(InvalidTag):
            await registry.set_tag(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, tag="Bad Tag", actor_email=None)
        with pytest.raises(LookupError):
            await registry.set_tag(org_id=ORG_A, user_id=USER_1, model_id="m1", version=9, tag="approved", actor_email=None)
        await registry.set_tag(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, tag="approved", actor_email="a@b.c")
        versions = await registry.list_versions(org_id=ORG_A, user_id=USER_1, model_id="m1")
        assert "approved" in versions[0]["tags"]

    run_with_db(settings, body)


def test_legacy_versions_without_latest_are_backfilled_on_read(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        assert (await registry.list_versions(org_id=ORG_A, user_id=USER_1, model_id="m1"))[0]["tags"] == ["latest"]

    run_with_db(settings, body)


def test_put_tag_route_moves_the_tag_and_rejects_invalid_names(api, raw_db):
    _seed_sync(raw_db)
    response = api.put("/api/v1/models/m1/versions/1/tags/approved", headers=HEADERS)
    assert response.status_code == 200
    assert "approved" in response.json()["versions"][0]["tags"]
    assert api.put("/api/v1/models/m1/versions/1/tags/Bad", headers=HEADERS).status_code == 422
    assert api.put("/api/v1/models/m1/versions/9/tags/approved", headers=HEADERS).status_code == 404


def test_mmm_run_passes_the_requesting_email_to_the_job():
    class EmailService(RecordingService):
        actor_email = "unset"

        async def submit_mmm_plan(self, *, org_id, user_id, chat_id, plan, model_name=None, actor_email=None):
            self.actor_email = actor_email
            return "job-123"

    service = EmailService()
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1", actor_email="who@x.io"))
    try:
        asyncio.run(StartMmmRunTool().ainvoke(tool_args()))
    finally:
        bind_scope(None)
    assert service.actor_email == "who@x.io"
