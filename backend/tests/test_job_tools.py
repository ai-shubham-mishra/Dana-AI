import asyncio
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from agent.tools.ml_ops.chores.check_last_job import CheckLastJobTool
from agent.tools.ml_ops.chores.check_last_model_run import CheckLastModelRunTool
from agent.tools.ml_ops.chores.check_latest_model import CheckLatestModelTool
from agent.tools.ml_ops.ml.training.check_job_status import CheckJobStatusTool
from integrations.training.scope import JobScope, bind_scope
from integrations.training.service import TrainingService
from tests.test_api import ORG_A, ORG_B, TEST_DB, USER_1, USER_2, make_settings
from tests.test_connector_tools import run_tool


class FakeService:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)
        self.calls: list[dict] = []

    async def find_latest_job(self, **kwargs):
        self.calls.append(kwargs)
        kind, statuses = kwargs.get("kind"), kwargs.get("statuses")
        matches = [
            j for j in self.jobs
            if (kind is None or j["kind"] == kind) and (statuses is None or j["status"] in statuses)
        ]
        return matches[0] if matches else None

    async def get_job(self, **kwargs):
        self.calls.append(kwargs)
        return next((j for j in self.jobs if j["id"] == kwargs["job_id"]), None)


def job_doc(job_id, *, status="succeeded", kind="mmm_training", created=datetime(2025, 1, 2, 9, 0), **extra):
    doc = {
        "id": job_id,
        "title": "MMM training · sales · 2024-01-01 to 2024-12-31",
        "kind": kind,
        "status": status,
        "stage": "done",
        "percent": 100,
        "message": "Model trained and saved",
        "error": None,
        "params": {"kpi": "sales", "channels": ["TV", "YouTube"], "date_start": "2024-01-01", "date_end": "2024-12-31"},
        "metrics": {"rows": 180, "divergences": 0, "max_rhat": 1.01},
        "artifact": {
            "name": "mmm_model.nc",
            "blob_container": "dana-ai-files",
            "blob_path": f"models/{ORG_A}/{USER_1}/{job_id}/mmm_model.nc",
            "bytes": 1024,
        },
        "created_at": created,
        "updated_at": created,
    }
    doc.update(extra)
    return doc


def scoped(service) -> None:
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1"))


def test_check_last_job_maps_family_to_kind_and_scopes_to_user():
    service = FakeService([job_doc("job-1", status="running")])
    scoped(service)
    out = run_tool(CheckLastJobTool(), {"model_family": "MMM"})
    assert service.calls == [{"org_id": ORG_A, "user_id": USER_1, "kind": "mmm_training"}]
    assert out.startswith("Job job-1:")
    assert "Status: running" in out


def test_check_last_job_reports_when_no_jobs_exist():
    scoped(FakeService([]))
    assert run_tool(CheckLastJobTool(), {}) == "No training jobs found for this user yet."
    scoped(FakeService([]))
    assert run_tool(CheckLastJobTool(), {"model_family": "mmm"}) == "No mmm jobs found for this user yet."


def test_check_latest_model_only_considers_succeeded_jobs_and_shows_artifact():
    service = FakeService([job_doc("job-2", status="failed", error="boom"), job_doc("job-1")])
    scoped(service)
    out = run_tool(CheckLatestModelTool(), {"model_family": "mmm"})
    assert service.calls == [{"org_id": ORG_A, "user_id": USER_1, "kind": "mmm_training", "statuses": ("succeeded",)}]
    assert out.startswith("Model from job job-1:")
    assert "KPI: sales" in out
    assert "Channels: TV, YouTube" in out
    assert "Date range: 2024-01-01 to 2024-12-31" in out
    assert "Artifact: mmm_model.nc (1024 bytes)" in out
    assert f"Saved at: dana-ai-files/models/{ORG_A}/{USER_1}/job-1/mmm_model.nc" in out
    assert "  rows: 180" in out


def test_check_latest_model_reports_when_nothing_succeeded():
    scoped(FakeService([job_doc("job-1", status="failed", error="boom")]))
    assert run_tool(CheckLatestModelTool(), {}) == "No trained model found for this user yet."


def test_check_last_model_run_includes_failed_runs_with_error_and_metrics():
    service = FakeService([job_doc("job-1", status="failed", error="boom", metrics=None)])
    scoped(service)
    out = run_tool(CheckLastModelRunTool(), {"model_family": "mmm"})
    assert service.calls == [{"org_id": ORG_A, "user_id": USER_1, "kind": "mmm_training", "statuses": ("succeeded", "failed")}]
    assert "Status: failed" in out
    assert "Error: boom" in out
    assert "Metrics:" not in out


def test_check_last_model_run_shows_metrics_for_succeeded_runs():
    scoped(FakeService([job_doc("job-1")]))
    out = run_tool(CheckLastModelRunTool(), {})
    assert "Status: succeeded" in out
    assert "Metrics:\n  rows: 180\n  divergences: 0\n  max_rhat: 1.01" in out


def test_check_job_status_looks_up_by_id_within_scope():
    service = FakeService([job_doc("job-1", status="running", percent=40, stage="sampling")])
    scoped(service)
    out = run_tool(CheckJobStatusTool(), {"job_id": "job-1"})
    assert service.calls == [{"org_id": ORG_A, "user_id": USER_1, "job_id": "job-1"}]
    assert "Status: running (sampling, 40%)" in out


def test_check_job_status_reports_unknown_job_as_error():
    scoped(FakeService([]))
    out = run_tool(CheckJobStatusTool(), {"job_id": "missing"})
    assert out == "Error: No training job with id missing was found for this user."


def test_job_tools_refuse_to_run_without_a_scope():
    bind_scope(None)
    for tool, args in [
        (CheckLastJobTool(), {}),
        (CheckLatestModelTool(), {}),
        (CheckLastModelRunTool(), {}),
        (CheckJobStatusTool(), {"job_id": "job-1"}),
    ]:
        assert run_tool(tool, args).startswith("Error:")


def test_service_reads_are_scoped_to_the_signed_in_user_and_org():
    settings = make_settings()

    async def scenario():
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        db = client[TEST_DB]
        await db.jobs.delete_many({})
        await db.jobs.insert_many([
            {**job_doc("old", created=datetime(2025, 1, 1)), "org_id": ORG_A, "user_id": USER_1, "chat_id": "c1"},
            {**job_doc("new", status="failed", created=datetime(2025, 1, 2)), "org_id": ORG_A, "user_id": USER_1, "chat_id": "c1"},
            {**job_doc("other-user", created=datetime(2025, 1, 4)), "org_id": ORG_A, "user_id": USER_2, "chat_id": "c2"},
            {**job_doc("other-org", created=datetime(2025, 1, 5)), "org_id": ORG_B, "user_id": USER_1, "chat_id": "c3"},
        ])
        service = TrainingService(db=db, blob=None, settings=settings)
        try:
            latest = await service.find_latest_job(org_id=ORG_A, user_id=USER_1)
            succeeded = await service.find_latest_job(org_id=ORG_A, user_id=USER_1, statuses=("succeeded",))
            foreign = await service.get_job(org_id=ORG_A, user_id=USER_1, job_id="other-user")
            own = await service.get_job(org_id=ORG_A, user_id=USER_1, job_id="old")
        finally:
            await db.jobs.delete_many({})
            client.close()
        return latest, succeeded, foreign, own

    latest, succeeded, foreign, own = asyncio.run(scenario())
    assert latest["id"] == "new"
    assert succeeded["id"] == "old"
    assert foreign is None
    assert own["id"] == "old"
    assert not {"_id", "org_id", "user_id", "chat_id"} & set(own)
