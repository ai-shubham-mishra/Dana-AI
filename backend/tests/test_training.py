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
    raw_db.jobs.insert_many(
        [
            {"id": "running-job", "title": "Running", "kind": "mmm_training", "status": "running",
             "org_id": ORG_A, "user_id": USER_1, "created_at": _dt(now), "updated_at": _dt(now)},
            {"id": "other-job", "title": "Other", "kind": "mmm_training", "status": "succeeded",
             "org_id": ORG_A, "user_id": USER_2, "created_at": _dt(now), "updated_at": _dt(now)},
        ]
    )
    with make_client("ok", tmp_path) as client:
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


def _dt(epoch: float):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc)
