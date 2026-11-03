import functools
import json
import sys
import time

import pytest
from azure.storage.blob import BlobServiceClient
from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import BACKEND_ROOT, Settings
from integrations.training.mmm.request import RequestError, load_dataset_spec, validate_request
from tests.test_api import ORG_A, USER_1, USER_2, auth, make_settings, member, mint, raw_db, settings, static_secret  # noqa: F401

HEADERS = auth(mint())
MMM_DIR = BACKEND_ROOT / "resources" / "training" / "mmm"
SPEC = load_dataset_spec(MMM_DIR / "mmm_demo.yaml")


def test_default_run_folder_is_repo_var_training_outside_reload_watched_tree():
    default = Settings.model_fields["training_output_dir"].default
    assert default == BACKEND_ROOT.parent / "var" / "training"
    assert not default.is_relative_to(BACKEND_ROOT)

FAKE_TRAINER = """
import json, pathlib, sys
job_dir, outcome = pathlib.Path(sys.argv[1]), sys.argv[2]
print("@@progress " + json.dumps({"stage": "sampling", "percent": 40, "message": "Sampling"}), flush=True)
if outcome == "ok":
    job_dir.mkdir(parents=True, exist_ok=True)
    model = job_dir / "mmm_model.nc"
    model.write_bytes(b"fake-model")
    metrics = {"rows": 180, "divergences": 0, "max_rhat": 1.01, "channels": ["TV"]}
    print("@@result " + json.dumps({"status": "success", "model_path": str(model), "model_bytes": 10, "metrics": metrics}), flush=True)
    sys.exit(0)
print("@@result " + json.dumps({"status": "error", "message": "boom"}), flush=True)
sys.exit(1)
"""

SUBMIT = {
    "model": "mmm",
    "kpi": "sales",
    "channels": ["TV", "YouTube"],
    "date_range": "2024-01-01 to 2024-12-31",
}


def fake_trainer(outcome: str):
    return lambda job_dir, request: [sys.executable, "-c", FAKE_TRAINER, str(job_dir), outcome]


def real_small_trainer(job_dir, request):
    return [
        sys.executable, "-m", "integrations.training.mmm.cli",
        "--data", str(MMM_DIR / "mmm_demo.csv"),
        "--config", str(MMM_DIR / "mmm_demo.yaml"),
        "--output-dir", str(job_dir),
        "--request", json.dumps(request.to_dict()),
        "--chains", "2", "--tune", "100", "--draws", "100",
    ]


def make_client(outcome_or_factory, output_dir):
    settings = make_settings(training_output_dir=output_dir)
    factory = fake_trainer(outcome_or_factory) if isinstance(outcome_or_factory, str) else outcome_or_factory
    app = create_app(settings, jwt_secret_loader=static_secret, training_command_factory=factory)
    return TestClient(app)


def submit(client, **overrides):
    kwargs = {"org_id": ORG_A, "user_id": USER_1, "chat_id": "chat-1", **SUBMIT, **overrides}
    return client.portal.call(functools.partial(client.app.state.training.submit, **kwargs))


def wait_for(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while True:
        body = client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).json()
        if body["status"] in ("succeeded", "failed") or time.time() > deadline:
            return body
        time.sleep(0.1)


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"model": "pmm"}, "mmm"),
        ({"kpi": "revenue"}, "sales"),
        ({"channels": ["meta"]}, "meta"),
        ({"channels": []}, "channel"),
        ({"date_range": "2024-01-01"}, "date"),
        ({"date_range": "2025-01-01 to 2024-01-01"}, "start"),
    ],
)
def test_invalid_requests_are_rejected_with_a_reason(overrides, fragment):
    args = {**SUBMIT, **overrides}
    with pytest.raises(RequestError) as exc:
        validate_request(spec=SPEC, **args)
    assert fragment in str(exc.value).lower()


def test_valid_request_is_normalised():
    request = validate_request(spec=SPEC, **SUBMIT)
    assert request.kpi == "sales"
    assert set(request.channels) == {"TV", "YouTube"}
    assert (request.date_start, request.date_end) == ("2024-01-01", "2024-12-31")


def test_successful_job_records_progress_metrics_and_artifact(raw_db, member, tmp_path):
    with make_client("ok", tmp_path) as client:
        job_id = submit(client)
        body = wait_for(client, job_id)
        assert body["status"] == "succeeded", body
        assert body["percent"] == 100
        assert body["metrics"]["divergences"] == 0
        assert body["artifact"] == {"name": "mmm_model.nc", "bytes": len(b"fake-model")}
        assert body["artifacts"] == [{"name": "mmm_model.nc", "bytes": len(b"fake-model")}]
        assert "blob_path" not in json.dumps(body)
        assert [e["stage"] for e in body["events"]][-1] == "done"

        stored = raw_db.jobs.find_one({"id": job_id})
        blob = BlobServiceClient.from_connection_string(client.app.state.settings.blob_connection_string)
        data = blob.get_blob_client(stored["artifact"]["blob_container"], stored["artifact"]["blob_path"]).download_blob().readall()
        assert data == b"fake-model"


def test_removing_a_job_deletes_every_stored_run_file(tmp_path):
    import asyncio
    import types

    from integrations.training.service import TrainingService

    deleted = []

    class Container:
        async def delete_blob(self, name):
            deleted.append(name)

    stub = types.SimpleNamespace(
        _blob=types.SimpleNamespace(get_container_client=lambda name: Container()),
        _settings=types.SimpleNamespace(blob_container="c", training_output_dir=tmp_path),
    )
    artifact = {
        "name": "mmm_model.nc", "blob_container": "c", "blob_path": "models/o/u/job-1/mmm_model.nc",
        "stored": ["mmm_model.nc", "config.yml"],
    }
    asyncio.run(TrainingService._remove_job_files(stub, "job-1", artifact))
    assert deleted == ["models/o/u/job-1/mmm_model.nc", "models/o/u/job-1/config.yml"]

    deleted.clear()
    legacy = {"name": "mmm_model.nc", "blob_container": "c", "blob_path": "models/o/u/job-2/mmm_model.nc"}
    asyncio.run(TrainingService._remove_job_files(stub, "job-2", legacy))
    assert deleted == ["models/o/u/job-2/mmm_model.nc"]


def test_store_run_files_uploads_present_run_files_under_the_job(tmp_path):
    import asyncio
    import types

    from integrations.training.service import TrainingService, run_blob_path

    uploads = {}

    class Container:
        async def upload_blob(self, name, data, overwrite):
            uploads[name] = data

    stub = types.SimpleNamespace(
        _blob=types.SimpleNamespace(get_container_client=lambda name: Container()),
        _settings=types.SimpleNamespace(blob_container="c"),
    )
    (tmp_path / "config.yml").write_text("a: 1", encoding="utf-8")
    (tmp_path / "dataset.csv").write_text("x,y", encoding="utf-8")
    (tmp_path / "mmm_model.nc").write_bytes(b"model")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    stored = asyncio.run(TrainingService._store_run_files(stub, "org", "user", "job-9", tmp_path))
    assert sorted(stored) == ["config.yml", "dataset.csv"]
    assert uploads == {
        run_blob_path("org", "user", "job-9", "config.yml"): b"a: 1",
        run_blob_path("org", "user", "job-9", "dataset.csv"): b"x,y",
    }


def test_plan_run_stores_every_run_file_end_to_end(raw_db, member, tmp_path, monkeypatch):
    from integrations.training import service as training_service
    from integrations.training.mmm.dataset import DatasetResult
    from integrations.training.mmm.run_folder import RUN_FILES
    from integrations.training.mmm.sandbox import SandboxOutcome
    from tests.test_mmm_run import make_plan

    async def fake_validate(pool, schema, plan):
        return None

    async def fake_build(pool, schema, org_id, plan):
        return DatasetResult(columns=["date", "revenue"], rows=[{"date": "2024-01-01", "revenue": 1.0}],
                             log={"rows_kept": 1})

    async def fake_run_script(command, run_dir, on_progress, env=None):
        (run_dir / "evaluation.json").write_text("{}", encoding="utf-8")
        (run_dir / "mmm_model.nc").write_bytes(b"fake-model")
        return SandboxOutcome(code=0, result={"status": "success", "metrics": {"divergences": 0}}, tail=[])

    monkeypatch.setattr(training_service, "validate_sources", fake_validate)
    monkeypatch.setattr(training_service, "build_dataset", fake_build)
    monkeypatch.setattr(training_service, "run_script", fake_run_script)

    with make_client("ok", tmp_path) as client:
        svc = client.app.state.training
        svc._connector_pool = object()

        async def fake_name_check(**kwargs):
            return "Plan Model"

        monkeypatch.setattr(svc, "_check_new_model_name", fake_name_check)
        job_id = client.portal.call(functools.partial(
            svc.submit_mmm_plan, org_id=ORG_A, user_id=USER_1, chat_id="chat-1",
            plan=make_plan(), model_name="Plan Model",
        ))
        body = wait_for(client, job_id)
        assert body["status"] == "succeeded", body

        stored = raw_db.jobs.find_one({"id": job_id})["artifact"]["stored"]
        assert sorted(stored) == sorted(RUN_FILES)
        for name in RUN_FILES:
            data = client.portal.call(functools.partial(
                svc.read_run_file, org_id=ORG_A, user_id=USER_1, job_id=job_id, name=name,
            ))
            assert data is not None, name


def test_store_run_files_raises_naming_the_file_that_failed(tmp_path):
    import asyncio
    import types

    import pytest

    from integrations.training.service import ArtifactUploadError, TrainingService

    class Container:
        async def upload_blob(self, name, data, overwrite):
            if name.endswith("config.yml"):
                raise OSError("network reset")

    stub = types.SimpleNamespace(
        _blob=types.SimpleNamespace(get_container_client=lambda name: Container()),
        _settings=types.SimpleNamespace(blob_container="c"),
    )
    (tmp_path / "config.yml").write_text("a: 1", encoding="utf-8")
    with pytest.raises(ArtifactUploadError, match="could not store config.yml"):
        asyncio.run(TrainingService._store_run_files(stub, "org", "user", "job-9", tmp_path))


def test_plan_run_fails_and_records_no_version_when_a_run_file_upload_fails(raw_db, member, tmp_path, monkeypatch):
    from integrations.training import service as training_service
    from integrations.training.mmm.dataset import DatasetResult
    from integrations.training.mmm.sandbox import SandboxOutcome
    from tests.test_mmm_run import make_plan

    async def fake_validate(pool, schema, plan):
        return None

    async def fake_build(pool, schema, org_id, plan):
        return DatasetResult(columns=["date", "revenue"], rows=[{"date": "2024-01-01", "revenue": 1.0}],
                             log={"rows_kept": 1})

    async def fake_run_script(command, run_dir, on_progress, env=None):
        (run_dir / "evaluation.json").write_text("{}", encoding="utf-8")
        (run_dir / "mmm_model.nc").write_bytes(b"fake-model")
        return SandboxOutcome(code=0, result={"status": "success", "metrics": {}}, tail=[])

    class FailingContainer:
        def __init__(self, inner):
            self._inner = inner

        async def upload_blob(self, name, data, overwrite):
            if name.endswith("dataset.csv"):
                raise OSError("network reset")
            return await self._inner.upload_blob(name=name, data=data, overwrite=overwrite)

    monkeypatch.setattr(training_service, "validate_sources", fake_validate)
    monkeypatch.setattr(training_service, "build_dataset", fake_build)
    monkeypatch.setattr(training_service, "run_script", fake_run_script)

    with make_client("ok", tmp_path) as client:
        svc = client.app.state.training
        svc._connector_pool = object()
        real_container = svc._blob.get_container_client
        monkeypatch.setattr(svc._blob, "get_container_client",
                            lambda name: FailingContainer(real_container(name)))

        async def fake_name_check(**kwargs):
            return "Plan Model"

        monkeypatch.setattr(svc, "_check_new_model_name", fake_name_check)
        job_id = client.portal.call(functools.partial(
            svc.submit_mmm_plan, org_id=ORG_A, user_id=USER_1, chat_id="chat-1",
            plan=make_plan(), model_name="Plan Model",
        ))
        body = wait_for(client, job_id)
        assert body["status"] == "failed", body
        assert "could not store dataset.csv" in body["error"]
        assert raw_db.jobs.find_one({"id": job_id})["artifact"] is None
        assert raw_db.model_versions.count_documents({"job_id": job_id}) == 0


def test_failed_job_records_the_trainer_error(raw_db, member, tmp_path):
    with make_client("fail", tmp_path) as client:
        job_id = submit(client)
        body = wait_for(client, job_id)
        assert body["status"] == "failed"
        assert body["error"] == "boom"
        assert body["artifact"] is None


def test_job_detail_is_tenant_isolated(raw_db, member, tmp_path):
    now = time.time()
    raw_db.jobs.insert_one(
        {"id": "other-job", "title": "Other", "kind": "mmm_training", "status": "queued",
         "org_id": ORG_A, "user_id": USER_2, "created_at": _dt(now), "updated_at": _dt(now)}
    )
    with make_client("ok", tmp_path) as client:
        assert client.get("/api/v1/jobs/other-job", headers=HEADERS).status_code == 404
        assert client.get("/api/v1/jobs/missing", headers=HEADERS).status_code == 404


def test_delete_removes_job_events_artifact_and_run_folder(raw_db, member, tmp_path):
    with make_client("ok", tmp_path) as client:
        job_id = submit(client)
        assert wait_for(client, job_id)["status"] == "succeeded"
        artifact = raw_db.jobs.find_one({"id": job_id})["artifact"]
        blob = BlobServiceClient.from_connection_string(client.app.state.settings.blob_connection_string)
        blob_client = blob.get_blob_client(artifact["blob_container"], artifact["blob_path"])
        assert blob_client.exists()
        assert (tmp_path / job_id).is_dir()

        response = client.post("/api/v1/jobs/delete", json={"job_ids": [job_id]}, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.json() == {"deleted": [job_id], "skipped": []}
        assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).status_code == 404
        assert raw_db.job_events.count_documents({"job_id": job_id}) == 0
        assert not (tmp_path / job_id).exists()
        assert not blob_client.exists()


def test_delete_skips_running_missing_and_other_users_jobs(raw_db, member, tmp_path):
    now = time.time()
    with make_client("ok", tmp_path) as client:
        raw_db.jobs.insert_many(
            [
                {"id": "running-job", "title": "Running", "kind": "mmm_training", "status": "running",
                 "org_id": ORG_A, "user_id": USER_1, "created_at": _dt(now), "updated_at": _dt(now)},
                {"id": "other-job", "title": "Other", "kind": "mmm_training", "status": "succeeded",
                 "org_id": ORG_A, "user_id": USER_2, "created_at": _dt(now), "updated_at": _dt(now)},
            ]
        )
        response = client.post(
            "/api/v1/jobs/delete", json={"job_ids": ["running-job", "other-job", "missing"]}, headers=HEADERS
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "deleted": [],
            "skipped": [
                {"id": "running-job", "reason": "Job is still running"},
                {"id": "other-job", "reason": "Job not found"},
                {"id": "missing", "reason": "Job not found"},
            ],
        }
        assert raw_db.jobs.count_documents({"id": {"$in": ["running-job", "other-job"]}}) == 2
        assert client.post("/api/v1/jobs/delete", json={"job_ids": []}, headers=HEADERS).status_code == 422


def test_delete_keeps_job_when_file_cleanup_fails(raw_db, member, tmp_path, monkeypatch):
    with make_client("ok", tmp_path) as client:
        job_id = submit(client)
        assert wait_for(client, job_id)["status"] == "succeeded"

        async def fail(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(client.app.state.training, "_remove_job_files", fail)
        response = client.post("/api/v1/jobs/delete", json={"job_ids": [job_id]}, headers=HEADERS)
        assert response.json() == {
            "deleted": [],
            "skipped": [{"id": job_id, "reason": "Files could not be removed; try again"}],
        }
        assert raw_db.jobs.find_one({"id": job_id}) is not None
        assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).status_code == 200


def test_real_mmm_trainer_runs_end_to_end(raw_db, member, tmp_path):
    with make_client(real_small_trainer, tmp_path) as client:
        job_id = submit(client)
        body = wait_for(client, job_id, timeout=300)
        assert body["status"] == "succeeded", body
        assert body["metrics"]["channels"]
        assert body["artifact"]["bytes"] > 1_000_000
        stored = raw_db.jobs.find_one({"id": job_id})["artifact"]["stored"]
        assert stored == ["mmm_model.nc"]


def _dt(epoch: float):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc)
