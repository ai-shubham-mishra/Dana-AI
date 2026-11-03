import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pymongo.errors import DuplicateKeyError

from integrations.deployments.logs import append_line, tail_lines
from integrations.deployments.probe import probe
from integrations.model_registry.registry import ARCHIVE_RETENTION

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("provisioning", "running")
LIST_LIMIT = 50
PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
HIDDEN_FIELDS = ("_id", "org_id", "user_id")


class DeploymentBusy(RuntimeError):
    pass


class DeprovisionFailed(RuntimeError):
    pass


class VersionAlreadyDeployed(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _public(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in HIDDEN_FIELDS}


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


class DeploymentService:
    def __init__(
        self,
        *,
        db: Any,
        registry: Any,
        orchestrator: Any,
        leases: Any,
        logs_dir: Path,
        http: httpx.AsyncClient,
    ):
        self._db = db
        self._registry = registry
        self._orchestrator = orchestrator
        self._leases = leases
        self._logs_dir = logs_dir
        self._http = http
        self._followers: dict[str, Any] = {}
        self._tasks: set[asyncio.Task] = set()
        logs_dir.mkdir(parents=True, exist_ok=True)

    def log_path(self, dep_id: str) -> Path:
        return self._logs_dir / f"{dep_id}.log"

    async def allocate(
        self, *, org_id: str, user_id: str, model_id: str, version: int, actor_email: str | None
    ) -> dict[str, Any]:
        found = await self._registry.get_version(
            org_id=org_id, user_id=user_id, model_id=model_id, version=version
        )
        if found is None:
            raise LookupError(f"model {model_id} has no version {version}")
        active = await self._db.deployments.find_one(
            {"model_id": model_id, "version": version, "status": {"$in": list(ACTIVE_STATUSES)}},
            {"_id": 0, "id": 1},
        )
        if active is not None:
            raise VersionAlreadyDeployed(
                f"Version {version} already has an active container ({active['id']}); deallocate it first"
            )
        dep_id = uuid.uuid4().hex[:12]
        port = await self._leases.acquire(dep_id)
        now = _now()
        doc = {
            "id": dep_id,
            "org_id": org_id,
            "user_id": user_id,
            "model_id": model_id,
            "version": version,
            "job_id": found["job_id"],
            "active": True,
            "status": "provisioning",
            "host_port": port,
            "container": self._orchestrator.container_name(dep_id),
            "message": "Building the container image",
            "stage": "Queued",
            "percent": 0,
            "error": None,
            "created_by_email": actor_email,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self._db.deployments.insert_one(doc)
        except DuplicateKeyError as exc:
            await self._leases.release(dep_id)
            raise VersionAlreadyDeployed(f"Version {version} already has an active container") from exc
        except Exception:
            await self._leases.release(dep_id)
            raise
        self.log_path(dep_id).touch()
        await self._registry.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action="deployment_allocated",
            version=version, actor_email=actor_email, detail=f"deployment {dep_id} on port {port}",
        )
        task = asyncio.create_task(
            self._provision(dep_id, org_id, user_id, model_id, version, found["job_id"], port)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return _public(doc)

    async def deallocate(self, *, org_id: str, user_id: str, dep_id: str, actor_email: str | None) -> None:
        doc = await self.find(org_id=org_id, user_id=user_id, dep_id=dep_id)
        if doc["status"] == "provisioning":
            raise DeploymentBusy("Deployment is still provisioning; wait for it to finish before deallocating")
        if doc["status"] in ("stopped", "failed"):
            return
        try:
            await self._teardown(dep_id, strict=True)
        except Exception as exc:
            logger.exception("Could not stop container for deployment %s", dep_id)
            await self._update(dep_id, error=f"Could not stop container: {exc}")
            raise DeprovisionFailed(f"Could not stop the container, it is still running: {exc}") from exc
        now = _now()
        append_line(self.log_path(dep_id), "Container deprovisioned")
        await self._update(
            dep_id, status="stopped", message="Deallocated", error=None,
            archived_at=now, purge_at=now + ARCHIVE_RETENTION,
        )
        await self._registry.record_event(
            org_id=org_id, user_id=user_id, model_id=doc["model_id"], action="deployment_stopped",
            version=doc["version"], actor_email=actor_email, detail=f"deployment {dep_id} deallocated",
        )

    async def find(self, *, org_id: str, user_id: str, dep_id: str) -> dict[str, Any]:
        doc = await self._db.deployments.find_one(
            {"id": dep_id, "org_id": org_id, "user_id": user_id}, PROJECTION
        )
        if doc is None:
            raise LookupError("Deployment not found")
        return doc

    async def list_deployments(self, *, org_id: str, user_id: str, model_id: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"org_id": org_id, "user_id": user_id, "archived_at": None}
        if model_id:
            query["model_id"] = model_id
        cursor = self._db.deployments.find(query, PROJECTION).sort("created_at", -1).limit(LIST_LIMIT)
        return await self._with_health([doc async for doc in cursor])

    async def list_archived(self, *, org_id: str, user_id: str) -> list[dict[str, Any]]:
        query = {"org_id": org_id, "user_id": user_id, "archived_at": {"$ne": None}}
        cursor = self._db.deployments.find(query, PROJECTION).sort("archived_at", -1).limit(LIST_LIMIT)
        return [doc async for doc in cursor]

    async def purge_due(self) -> int:
        purged = 0
        async for doc in self._db.deployments.find({"purge_at": {"$lte": _now()}}, {"_id": 0, "id": 1}):
            self.log_path(doc["id"]).unlink(missing_ok=True)
            await self._db.deployments.delete_one({"id": doc["id"]})
            purged += 1
        return purged

    async def get(self, *, org_id: str, user_id: str, dep_id: str) -> dict[str, Any]:
        doc = await self.find(org_id=org_id, user_id=user_id, dep_id=dep_id)
        return (await self._with_health([doc]))[0]

    async def tail_logs(self, dep_id: str) -> AsyncIterator[str]:
        async def is_active() -> bool:
            doc = await self._db.deployments.find_one({"id": dep_id}, {"_id": 0, "status": 1})
            return doc is not None and doc["status"] in ACTIVE_STATUSES

        async for line in tail_lines(self.log_path(dep_id), is_active):
            yield line

    async def reconcile(self) -> None:
        cursor = self._db.deployments.find({"status": "provisioning"}, {"_id": 0, "id": 1, "model_id": 1, "version": 1, "org_id": 1, "user_id": 1})
        async for doc in cursor:
            logger.warning("Deployment %s was interrupted by a restart", doc["id"])
            await self._teardown(doc["id"])
            await self._update(doc["id"], status="failed", message="Provisioning failed",
                               error="Interrupted by a server restart")
            await self._registry.record_event(
                org_id=doc["org_id"], user_id=doc["user_id"], model_id=doc["model_id"],
                action="deployment_failed", version=doc["version"], actor_email=None,
                detail=f"deployment {doc['id']} interrupted by a restart",
            )

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for follower in list(self._followers.values()):
            await asyncio.to_thread(follower.stop)
        self._followers.clear()

    async def _provision(
        self, dep_id: str, org_id: str, user_id: str, model_id: str, version: int, job_id: str, port: int
    ) -> None:
        path = self.log_path(dep_id)
        loop = asyncio.get_running_loop()

        def sink(line: str) -> None:
            append_line(path, line)

        def progress(stage: str, percent: int) -> None:
            future = asyncio.run_coroutine_threadsafe(
                self._update(dep_id, stage=stage, percent=percent), loop
            )
            future.result(timeout=30)

        try:
            await asyncio.to_thread(
                self._orchestrator.provision, job_id, False, instance_id=dep_id, host_port=port,
                log=sink, progress=progress,
            )
            container = self._orchestrator.container_name(dep_id)
            self._followers[dep_id] = self._orchestrator.runtime.follow_logs(container, sink)
            await self._update(dep_id, status="running", message="Live", stage="Live", percent=100, error=None)
            sink(f"Deployment is live at {base_url(port)}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Deployment %s failed to provision", dep_id)
            sink(f"Provisioning failed: {exc}")
            await self._teardown(dep_id)
            await self._update(dep_id, status="failed", message="Provisioning failed", stage="Failed", error=str(exc))
            await self._registry.record_event(
                org_id=org_id, user_id=user_id, model_id=model_id, action="deployment_failed",
                version=version, actor_email=None, detail=f"deployment {dep_id} failed: {exc}",
            )

    async def _teardown(self, dep_id: str, *, strict: bool = False) -> None:
        follower = self._followers.pop(dep_id, None)
        if follower is not None:
            await asyncio.to_thread(follower.stop)
        try:
            await asyncio.to_thread(self._orchestrator.deprovision, dep_id)
        except Exception:
            logger.exception("Could not remove container for deployment %s", dep_id)
            if strict:
                raise
        await self._leases.release(dep_id)

    async def _with_health(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        healths = await asyncio.gather(*(self._health(doc) for doc in docs))
        return [{**_public(doc), "url": base_url(doc["host_port"]), "health": health}
                for doc, health in zip(docs, healths, strict=True)]

    async def _health(self, doc: dict[str, Any]) -> dict[str, Any]:
        if doc["status"] == "running":
            return await probe(self._http, base_url(doc["host_port"]))
        if doc["status"] == "provisioning":
            return {"state": "starting", "detail": doc.get("message")}
        return {"state": doc["status"], "detail": doc.get("error")}

    async def _update(self, dep_id: str, **fields: Any) -> None:
        update: dict[str, Any] = {"$set": {**fields, "updated_at": _now()}}
        if "status" in fields and fields["status"] not in ACTIVE_STATUSES:
            update["$unset"] = {"active": ""}
        await self._db.deployments.update_one({"id": dep_id}, update)
