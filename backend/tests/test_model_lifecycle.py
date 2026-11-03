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


def test_delete_model_archives_it_for_seven_days_instead_of_removing_it(api, raw_db):
    _seed_sync(raw_db)
    res = api.delete("/api/v1/models/m1", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["outcome"] == "archived"
    assert api.get("/api/v1/models", headers=HEADERS).json() == []
    assert api.get("/api/v1/models/m1", headers=HEADERS).status_code == 404
    archived = api.get("/api/v1/models/archive", headers=HEADERS).json()
    assert [m["id"] for m in archived] == ["m1"]
    assert archived[0]["versions"][0]["version"] == 1
    assert archived[0]["purge_at"] is not None
    assert raw_db.model_versions.find_one({"model_id": "m1"})["archived_at"] is not None


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


def test_deleting_the_last_version_archives_the_model(api, raw_db):
    _seed_sync(raw_db)
    res = api.delete("/api/v1/models/m1/versions/1", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["outcome"] == "archived"
    assert api.get("/api/v1/models/m1", headers=HEADERS).status_code == 404
    assert [m["id"] for m in api.get("/api/v1/models/archive", headers=HEADERS).json()] == ["m1"]


def test_deleting_unknown_model_or_version_is_not_found(api, raw_db):
    _seed_sync(raw_db)
    assert api.delete("/api/v1/models/missing", headers=HEADERS).status_code == 404
    assert api.delete("/api/v1/models/m1/versions/9", headers=HEADERS).status_code == 404


def test_restore_brings_an_archived_model_back_with_its_versions(api, raw_db):
    _seed_sync(raw_db)
    api.delete("/api/v1/models/m1", headers=HEADERS)
    res = api.post("/api/v1/models/m1/restore", headers=HEADERS)
    assert res.status_code == 200
    detail = res.json()
    assert detail["latest_version"] == 1
    assert [v["version"] for v in detail["versions"]] == [1]
    assert "latest" in detail["versions"][0]["tags"]
    assert api.get("/api/v1/models/archive", headers=HEADERS).json() == []
    stored = raw_db.model_versions.find_one({"model_id": "m1"})
    assert stored["archived_at"] is None and stored["purge_at"] is None


def test_restore_is_refused_while_another_model_uses_the_name(api, raw_db):
    _seed_sync(raw_db)
    api.delete("/api/v1/models/m1", headers=HEADERS)
    now = datetime.now(UTC)
    raw_db.models.insert_one({
        "id": "m2", "org_id": ORG_A, "user_id": USER_1, "name": "mmm · sales", "latest_version": 1,
        "version_count": 1, "created_at": now, "updated_at": now, "archived_at": None,
    })
    res = api.post("/api/v1/models/m1/restore", headers=HEADERS)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "name_taken"
    assert res.json()["detail"]["suggestions"]
    assert api.get("/api/v1/models/archive", headers=HEADERS).json()[0]["id"] == "m1"


def test_restore_of_a_live_or_unknown_model_is_not_found(api, raw_db):
    _seed_sync(raw_db)
    assert api.post("/api/v1/models/m1/restore", headers=HEADERS).status_code == 404
    assert api.post("/api/v1/models/missing/restore", headers=HEADERS).status_code == 404


def test_download_zips_the_model_file_and_manifest_for_archived_models_only(api, raw_db, monkeypatch):
    import io
    import json
    import zipfile

    _seed_sync(raw_db)
    assert api.get("/api/v1/models/m1/download", headers=HEADERS).status_code == 404
    api.delete("/api/v1/models/m1", headers=HEADERS)

    async def fake_read(*, org_id, user_id, job_id):
        return ("mmm_model.nc", b"MODEL-BYTES") if job_id == "job-1" else None

    monkeypatch.setattr(api.app.state.training, "read_model_file", fake_read)
    res = api.get("/api/v1/models/m1/download", headers=HEADERS)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert res.headers["content-disposition"] == 'attachment; filename="MMM-sales.zip"'
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        assert archive.read("v1/mmm_model.nc") == b"MODEL-BYTES"
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["model"]["name"] == "MMM · sales"
    assert manifest["versions"][0]["model_file"] == "v1/mmm_model.nc"
    assert manifest["versions"][0]["params"] == {}


def test_version_artifacts_list_marks_stored_files_and_falls_back_for_legacy_versions(api, raw_db):
    _seed_sync(raw_db)
    raw_db.model_versions.update_one(
        {"model_id": "m1", "version": 1},
        {"$set": {"artifact": {
            "name": "mmm_model.nc", "bytes": 10, "blob_path": "models/o/u/job-1/mmm_model.nc",
            "files": [{"name": "mmm_model.nc", "bytes": 10}, {"name": "config.yml", "bytes": 4}],
            "stored": ["mmm_model.nc", "config.yml"],
        }}},
    )
    listing = api.get("/api/v1/models/m1/versions/1/artifacts", headers=HEADERS)
    assert listing.status_code == 200
    assert listing.json() == [
        {"name": "mmm_model.nc", "bytes": 10, "stored": True},
        {"name": "config.yml", "bytes": 4, "stored": True},
    ]

    raw_db.model_versions.update_one(
        {"model_id": "m1", "version": 1},
        {"$set": {"artifact": {"name": "mmm_model.nc", "bytes": 7, "blob_path": "models/o/u/job-1/mmm_model.nc"}}},
    )
    legacy = api.get("/api/v1/models/m1/versions/1/artifacts", headers=HEADERS).json()
    assert legacy == [{"name": "mmm_model.nc", "bytes": 7, "stored": True}]

    assert api.get("/api/v1/models/m1/versions/9/artifacts", headers=HEADERS).status_code == 404
    assert api.get("/api/v1/models/missing/versions/1/artifacts", headers=HEADERS).status_code == 404


def test_version_artifact_download_serves_stored_files_only(api, raw_db, monkeypatch):
    _seed_sync(raw_db)
    raw_db.model_versions.update_one(
        {"model_id": "m1", "version": 1},
        {"$set": {"artifact": {
            "name": "mmm_model.nc", "bytes": 10, "blob_path": "models/o/u/job-1/mmm_model.nc",
            "files": [{"name": "mmm_model.nc", "bytes": 10}, {"name": "train.py", "bytes": 3}],
            "stored": ["mmm_model.nc"],
        }}},
    )

    async def fake_read(*, org_id, user_id, job_id, name):
        return b"NC-BYTES" if (job_id, name) == ("job-1", "mmm_model.nc") else None

    monkeypatch.setattr(api.app.state.training, "read_run_file", fake_read)
    res = api.get("/api/v1/models/m1/versions/1/artifacts/mmm_model.nc", headers=HEADERS)
    assert res.status_code == 200
    assert res.content == b"NC-BYTES"
    assert res.headers["content-disposition"] == 'attachment; filename="mmm_model.nc"'
    assert api.get("/api/v1/models/m1/versions/1/artifacts/train.py", headers=HEADERS).status_code == 404
    assert api.get("/api/v1/models/m1/versions/1/artifacts/nope.csv", headers=HEADERS).status_code == 404
    assert api.get("/api/v1/models/m1/versions/9/artifacts/mmm_model.nc", headers=HEADERS).status_code == 404


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


def test_retraining_with_a_model_id_adds_a_version_and_never_a_new_model(settings, raw_db):
    _seed_sync(raw_db)

    async def body(db):
        registry = ModelRegistry(db)
        models_before = await db.models.count_documents({})
        await registry.record_version(**_record_second_version())
        assert await db.models.count_documents({}) == models_before
        versions = await registry.list_versions(org_id=ORG_A, user_id=USER_1, model_id="m1")
        assert sorted(v["version"] for v in versions) == [1, 2]
        assert versions[0]["version"] == 2 and versions[0]["job_id"] == "job-2"

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

        async def submit_mmm_plan(self, **kwargs):
            self.actor_email = kwargs["actor_email"]
            return "job-123"

    service = EmailService()
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1", actor_email="who@x.io"))
    try:
        asyncio.run(StartMmmRunTool().ainvoke(tool_args()))
    finally:
        bind_scope(None)
    assert service.actor_email == "who@x.io"
