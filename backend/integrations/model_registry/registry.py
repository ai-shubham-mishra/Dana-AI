from datetime import UTC, datetime
from typing import Any

from pymongo import DESCENDING

ACTIVE_DEPLOYMENT_STATUSES = ("provisioning", "running")
VERSION_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
MODEL_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
EVENT_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
EVENT_LIMIT = 200


def _now() -> datetime:
    return datetime.now(UTC)


class ModelRegistry:
    def __init__(self, db: Any):
        self._db = db

    async def record_version(
        self,
        *,
        org_id: str,
        user_id: str,
        job_id: str,
        params: dict[str, Any],
        metrics: dict[str, Any] | None,
        artifact: dict[str, Any] | None,
        actor_email: str | None,
        name: str,
        kpi: str,
        model_id: str | None = None,
        source: str = "train",
        source_version: int | None = None,
    ) -> dict[str, Any]:
        scope = {"org_id": org_id, "user_id": user_id}
        now = _now()
        if model_id is None:
            model_id = job_id
            await self._db.models.insert_one(
                {
                    **scope,
                    "id": model_id,
                    "name": name,
                    "kpi": kpi,
                    "latest_version": 0,
                    "version_count": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if await self._db.models.find_one({**scope, "id": model_id}, {"_id": 1}) is None:
            raise LookupError(f"model {model_id} not found")
        latest = await self._db.model_versions.find_one(
            {**scope, "model_id": model_id}, {"version": 1}, sort=[("version", DESCENDING)]
        )
        version = (latest["version"] if latest else 0) + 1
        doc = {
            **scope,
            "model_id": model_id,
            "version": version,
            "job_id": job_id,
            "source": source,
            "source_version": source_version,
            "params": params,
            "metrics": metrics,
            "artifact": artifact,
            "created_by_email": actor_email,
            "created_at": now,
        }
        await self._db.model_versions.insert_one(doc)
        await self._db.models.update_one(
            {**scope, "id": model_id},
            {"$set": {"latest_version": version, "updated_at": now}, "$inc": {"version_count": 1}},
        )
        action = "trained" if source == "train" else "retrained"
        detail = f"v{version} from job {job_id[:8]}"
        if source_version is not None:
            detail += f" (retrain of v{source_version})"
        await self.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action=action,
            version=version, actor_email=actor_email, detail=detail,
        )
        return {k: v for k, v in doc.items() if k not in ("_id", "org_id", "user_id")}

    async def list_models(self, *, org_id: str, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = (
            self._db.models.find({"org_id": org_id, "user_id": user_id}, MODEL_PROJECTION)
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def get_model(self, *, org_id: str, user_id: str, model_id: str) -> dict[str, Any] | None:
        return await self._db.models.find_one({"org_id": org_id, "user_id": user_id, "id": model_id}, MODEL_PROJECTION)

    async def list_versions(self, *, org_id: str, user_id: str, model_id: str) -> list[dict[str, Any]]:
        cursor = self._db.model_versions.find(
            {"org_id": org_id, "user_id": user_id, "model_id": model_id}, VERSION_PROJECTION
        ).sort("version", DESCENDING)
        return [doc async for doc in cursor]

    async def get_version(self, *, org_id: str, user_id: str, model_id: str, version: int) -> dict[str, Any] | None:
        return await self._db.model_versions.find_one(
            {"org_id": org_id, "user_id": user_id, "model_id": model_id, "version": version}, VERSION_PROJECTION
        )

    async def version_for_job(self, *, org_id: str, user_id: str, job_id: str) -> dict[str, Any] | None:
        return await self._db.model_versions.find_one(
            {"org_id": org_id, "user_id": user_id, "job_id": job_id}, VERSION_PROJECTION
        )

    async def list_events(self, *, org_id: str, user_id: str, model_id: str) -> list[dict[str, Any]]:
        cursor = (
            self._db.model_events.find({"org_id": org_id, "user_id": user_id, "model_id": model_id}, EVENT_PROJECTION)
            .sort("created_at", DESCENDING)
            .limit(EVENT_LIMIT)
        )
        return [doc async for doc in cursor]

    async def record_event(
        self,
        *,
        org_id: str,
        user_id: str,
        model_id: str,
        action: str,
        actor_email: str | None,
        version: int | None = None,
        detail: str | None = None,
    ) -> None:
        await self._db.model_events.insert_one(
            {
                "org_id": org_id,
                "user_id": user_id,
                "model_id": model_id,
                "action": action,
                "version": version,
                "actor_email": actor_email,
                "detail": detail,
                "created_at": _now(),
            }
        )

    async def blocking_deployment(
        self, *, org_id: str, user_id: str, model_id: str, version: int
    ) -> dict[str, Any] | None:
        return await self._db.deployments.find_one(
            {
                "org_id": org_id,
                "user_id": user_id,
                "model_id": model_id,
                "version": version,
                "status": {"$in": list(ACTIVE_DEPLOYMENT_STATUSES)},
            },
            {"_id": 0, "id": 1, "status": 1},
        )

    async def delete_version(
        self, *, org_id: str, user_id: str, model_id: str, version: int, actor_email: str | None
    ) -> None:
        scope = {"org_id": org_id, "user_id": user_id, "model_id": model_id}
        await self._db.model_versions.delete_one({**scope, "version": version})
        await self.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action="version_deleted",
            version=version, actor_email=actor_email, detail=f"v{version} removed with its training job",
        )
        remaining = await self._db.model_versions.find_one(scope, {"version": 1}, sort=[("version", DESCENDING)])
        if remaining is None:
            await self._db.models.delete_one({"org_id": org_id, "user_id": user_id, "id": model_id})
            await self._db.model_events.delete_many(scope)
            return
        await self._db.models.update_one(
            {"org_id": org_id, "user_id": user_id, "id": model_id},
            {
                "$set": {"latest_version": remaining["version"], "updated_at": _now()},
                "$inc": {"version_count": -1},
            },
        )
