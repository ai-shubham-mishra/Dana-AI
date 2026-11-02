import asyncio
import threading
import time
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient

from api.main import create_app
from integrations.deployments.leases import NoPortAvailable, PortLeases
from integrations.deployments.service import DeploymentBusy, DeploymentService
from integrations.model_registry.registry import ModelRegistry
from tests.test_api import ORG_A, USER_1, auth, member, mint, raw_db, settings, static_secret  # noqa: F401

HEADERS = auth(mint())


class FakeFollower:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeRuntime:
    def __init__(self):
        self.followers: list[FakeFollower] = []

    def follow_logs(self, name, sink):
        follower = FakeFollower()
        self.followers.append(follower)
        return follower


class FakeOrchestrator:
    def __init__(self, gate: threading.Event | None = None, fail: bool = False):
        self.runtime = FakeRuntime()
        self.gate = gate
        self.fail = fail
        self.provisioned: list[tuple] = []
        self.removed: list[str] = []

    @staticmethod
    def container_name(instance_id):
        return f"dana-mmm-{instance_id}"

    def provision(self, run_id, deploy_cloud=True, *, instance_id=None, host_port=None, log=None):
        if self.gate is not None:
            self.gate.wait(5)
        log("Building the container image")
        if self.fail:
            raise RuntimeError("docker build failed")
        log("Starting the container")
        self.provisioned.append((run_id, instance_id, host_port))

    def deprovision(self, instance_id):
        self.removed.append(instance_id)


def health_client(*, healthy: bool = True, unreachable: bool = False) -> httpx.AsyncClient:
    def handler(request):
        if unreachable:
            raise httpx.ConnectError("refused", request=request)
        if healthy:
            return httpx.Response(200, json={"status": "ok", "model_loaded": True})
        return httpx.Response(200, json={"status": "ok", "model_loaded": False})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def seed_version(db, model_id="m1", version=1, job_id="job-1"):
    now = datetime.now(UTC)
    await db.models.insert_one({
        "id": model_id, "org_id": ORG_A, "user_id": USER_1, "name": "MMM · sales",
        "latest_version": version, "version_count": 1, "created_at": now, "updated_at": now,
    })
    await db.model_versions.insert_one({
        "org_id": ORG_A, "user_id": USER_1, "model_id": model_id, "version": version, "job_id": job_id,
        "source": "train", "source_version": None, "kpi": "sales", "params": {}, "metrics": {},
        "created_by_email": "a@b.c", "created_at": now,
    })


def make_service(db, orchestrator, *, http, logs_dir, port_range=range(9100, 9103)):
    registry = ModelRegistry(db)
    leases = PortLeases(db, port_range, is_free=lambda port: True)
    service = DeploymentService(
        db=db, registry=registry, orchestrator=orchestrator, leases=leases, logs_dir=logs_dir, http=http
    )
    return service


async def wait_idle(service):
    while service._tasks:
        await asyncio.gather(*list(service._tasks), return_exceptions=True)


def run_with_db(settings, body):
    async def main():
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        try:
            return await body(client[settings.mongo_db])
        finally:
            client.close()

    return asyncio.run(main())


@pytest.fixture(autouse=True)
def clean_db(raw_db):
    yield raw_db


def test_allocate_goes_live_and_deallocate_releases_port(settings, tmp_path):
    orch = FakeOrchestrator()

    async def body(db):
        await seed_version(db)
        service = make_service(db, orch, http=health_client(), logs_dir=tmp_path)
        created = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email="a@b.c")
        await wait_idle(service)
        dep = await service.get(org_id=ORG_A, user_id=USER_1, dep_id=created["id"])
        assert dep["status"] == "running"
        assert dep["health"]["state"] == "live"
        assert dep["url"] == f"http://127.0.0.1:{dep['host_port']}"
        assert orch.provisioned == [("job-1", created["id"], dep["host_port"])]
        assert await db.port_leases.count_documents({}) == 1

        await service.deallocate(org_id=ORG_A, user_id=USER_1, dep_id=created["id"], actor_email="a@b.c")
        dep = await service.get(org_id=ORG_A, user_id=USER_1, dep_id=created["id"])
        assert dep["status"] == "stopped"
        assert orch.removed == [created["id"]]
        assert orch.runtime.followers[0].stopped
        assert await db.port_leases.count_documents({}) == 0
        actions = {doc["action"] async for doc in db.model_events.find({"model_id": "m1"})}
        assert {"deployment_allocated", "deployment_stopped"} <= actions
        await service.close()

    run_with_db(settings, body)


def test_each_deployment_gets_its_own_port(settings, tmp_path):
    async def body(db):
        await seed_version(db)
        service = make_service(db, FakeOrchestrator(), http=health_client(), logs_dir=tmp_path)
        first = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        second = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        await wait_idle(service)
        ports = {
            (await service.get(org_id=ORG_A, user_id=USER_1, dep_id=doc["id"]))["host_port"]
            for doc in (first, second)
        }
        assert len(ports) == 2
        await service.close()

    run_with_db(settings, body)


def test_deallocate_is_refused_while_provisioning(settings, tmp_path):
    gate = threading.Event()

    async def body(db):
        await seed_version(db)
        service = make_service(db, FakeOrchestrator(gate=gate), http=health_client(), logs_dir=tmp_path)
        created = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        with pytest.raises(DeploymentBusy):
            await service.deallocate(org_id=ORG_A, user_id=USER_1, dep_id=created["id"], actor_email=None)
        gate.set()
        await wait_idle(service)
        dep = await service.get(org_id=ORG_A, user_id=USER_1, dep_id=created["id"])
        assert dep["status"] == "running"
        await service.close()

    run_with_db(settings, body)


def test_failed_provision_marks_failed_and_frees_port(settings, tmp_path):
    orch = FakeOrchestrator(fail=True)

    async def body(db):
        await seed_version(db)
        service = make_service(db, orch, http=health_client(), logs_dir=tmp_path)
        created = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        await wait_idle(service)
        dep = await service.get(org_id=ORG_A, user_id=USER_1, dep_id=created["id"])
        assert dep["status"] == "failed"
        assert dep["error"] == "docker build failed"
        assert await db.port_leases.count_documents({}) == 0
        assert orch.removed == [created["id"]]
        assert "deployment_failed" in {doc["action"] async for doc in db.model_events.find({"model_id": "m1"})}
        assert "Provisioning failed" in (tmp_path / f"{created['id']}.log").read_text()
        await service.close()

    run_with_db(settings, body)


def test_unknown_version_and_full_port_range_are_rejected(settings, tmp_path):
    async def body(db):
        await seed_version(db)
        service = make_service(db, FakeOrchestrator(), http=health_client(), logs_dir=tmp_path, port_range=range(9100, 9101))
        with pytest.raises(LookupError):
            await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=9, actor_email=None)
        await db.port_leases.insert_one({"_id": 9100, "owner": "someone-else"})
        with pytest.raises(NoPortAvailable):
            await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        assert await db.deployments.count_documents({}) == 0

    run_with_db(settings, body)


def test_restart_marks_interrupted_provisioning_failed(settings, tmp_path):
    async def body(db):
        await seed_version(db)
        now = datetime.now(UTC)
        await db.deployments.insert_one({
            "id": "dep-stuck", "org_id": ORG_A, "user_id": USER_1, "model_id": "m1", "version": 1,
            "job_id": "job-1", "status": "provisioning", "host_port": 9100, "container": "dana-mmm-dep-stuck",
            "message": "Building", "error": None, "created_at": now, "updated_at": now,
        })
        await db.port_leases.insert_one({"_id": 9100, "owner": "dep-stuck"})
        orch = FakeOrchestrator()
        service = make_service(db, orch, http=health_client(), logs_dir=tmp_path)
        await service.reconcile()
        dep = await db.deployments.find_one({"id": "dep-stuck"})
        assert dep["status"] == "failed"
        assert "restart" in dep["error"]
        assert await db.port_leases.count_documents({}) == 0
        assert orch.removed == ["dep-stuck"]
        await service.close()

    run_with_db(settings, body)


@pytest.mark.parametrize(
    ("http", "state"),
    [
        (lambda: health_client(healthy=False), "unhealthy"),
        (lambda: health_client(unreachable=True), "unreachable"),
    ],
)
def test_health_probe_reports_unhealthy_and_unreachable(settings, tmp_path, http, state):
    async def body(db):
        await seed_version(db)
        service = make_service(db, FakeOrchestrator(), http=http(), logs_dir=tmp_path)
        created = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        await wait_idle(service)
        dep = await service.get(org_id=ORG_A, user_id=USER_1, dep_id=created["id"])
        assert dep["health"]["state"] == state
        await service.close()

    run_with_db(settings, body)


def test_tail_logs_replays_history_and_ends_after_deallocate(settings, tmp_path):
    async def body(db):
        await seed_version(db)
        service = make_service(db, FakeOrchestrator(), http=health_client(), logs_dir=tmp_path)
        created = await service.allocate(org_id=ORG_A, user_id=USER_1, model_id="m1", version=1, actor_email=None)
        await wait_idle(service)
        await service.deallocate(org_id=ORG_A, user_id=USER_1, dep_id=created["id"], actor_email=None)
        lines = [line async for line in service.tail_logs(created["id"])]
        assert lines[0] == "Building the container image"
        assert "Starting the container" in lines
        assert any("is live" in line for line in lines)
        await service.close()

    run_with_db(settings, body)


@pytest.fixture()
def api(settings, raw_db, member, tmp_path, monkeypatch):
    monkeypatch.setenv("PROVISIONING_WORKDIR", str(tmp_path))
    gate = threading.Event()
    gate.set()
    orch = FakeOrchestrator(gate=gate)
    with TestClient(
        create_app(settings, jwt_secret_loader=static_secret, orchestrator_factory=lambda cfg: orch)
    ) as client:
        client.orch = orch
        client.gate = gate
        yield client


def _seed_sync(raw_db):
    now = datetime.now(UTC)
    raw_db.models.insert_one({
        "id": "m1", "org_id": ORG_A, "user_id": USER_1, "name": "MMM · sales", "latest_version": 1,
        "version_count": 1, "created_at": now, "updated_at": now,
    })
    raw_db.model_versions.insert_one({
        "org_id": ORG_A, "user_id": USER_1, "model_id": "m1", "version": 1, "job_id": "job-1", "source": "train",
        "source_version": None, "kpi": "sales", "params": {}, "metrics": {}, "created_by_email": "a@b.c",
        "created_at": now,
    })


def _wait_for_status(client, dep_id, status):
    for _ in range(200):
        body = client.get(f"/api/v1/deployments/{dep_id}", headers=HEADERS).json()
        if body["status"] == status:
            return body
        time.sleep(0.02)
    raise AssertionError(f"deployment never reached {status}")


def test_models_api_lists_and_details_a_model(api, raw_db):
    _seed_sync(raw_db)
    listing = api.get("/api/v1/models", headers=HEADERS)
    assert listing.status_code == 200
    assert [m["id"] for m in listing.json()] == ["m1"]
    detail = api.get("/api/v1/models/m1", headers=HEADERS).json()
    assert detail["versions"][0]["version"] == 1
    assert api.get("/api/v1/models/missing", headers=HEADERS).status_code == 404


def test_retrain_unknown_version_is_not_found(api, raw_db):
    _seed_sync(raw_db)
    assert api.post("/api/v1/models/m1/versions/9/retrain", headers=HEADERS).status_code == 404


def test_retrain_with_invalid_stored_config_is_bad_request(api, raw_db):
    _seed_sync(raw_db)
    res = api.post("/api/v1/models/m1/versions/1/retrain", headers=HEADERS)
    assert res.status_code == 400
    assert any("kpi" in str(err.get("loc", "")) for err in res.json()["detail"])


def test_deployment_api_allocates_blocks_deallocate_and_streams_logs(api, raw_db):
    _seed_sync(raw_db)
    api.gate.clear()
    created = api.post("/api/v1/models/m1/versions/1/deployments", headers=HEADERS)
    assert created.status_code == 202
    dep_id = created.json()["id"]
    assert created.json()["status"] == "provisioning"

    blocked = api.post(f"/api/v1/deployments/{dep_id}/deallocate", headers=HEADERS)
    assert blocked.status_code == 409

    api.gate.set()
    assert _wait_for_status(api, dep_id, "running")["health"]["state"] == "unreachable"
    listed = api.get("/api/v1/deployments", params={"model_id": "m1"}, headers=HEADERS).json()
    assert [d["id"] for d in listed] == [dep_id]

    stopped = api.post(f"/api/v1/deployments/{dep_id}/deallocate", headers=HEADERS)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    logs = api.get(f"/api/v1/deployments/{dep_id}/logs", headers=HEADERS)
    assert logs.status_code == 200
    assert 'data: "Building the container image"' in logs.text
    assert "event: end" in logs.text
    assert api.get("/api/v1/deployments/missing", headers=HEADERS).status_code == 404
    assert api.get("/api/v1/deployments/missing/logs", headers=HEADERS).status_code == 404
