import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo import DESCENDING

ACTIVE_DEPLOYMENT_STATUSES = ("provisioning", "running")
VERSION_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
MODEL_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
EVENT_PROJECTION = {"_id": 0, "org_id": 0, "user_id": 0}
EVENT_LIMIT = 200
ARCHIVE_RETENTION = timedelta(days=7)
MODEL_NAME_MAX = 80
MODEL_NAME_RE = re.compile(r"^\w[\w \-.()·]*$")
NAME_SUFFIX_BYTES = 3
LATEST_TAG = "latest"
TAG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class InvalidModelName(ValueError):
    pass


class InvalidTag(ValueError):
    pass


class ModelNameTaken(Exception):
    def __init__(self, name: str, suggestions: list[str]):
        super().__init__(f"model name '{name}' is already used")
        self.name = name
        self.suggestions = suggestions


def normalize_model_name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if not name or len(name) > MODEL_NAME_MAX or not MODEL_NAME_RE.match(name):
        raise InvalidModelName(
            f"model name must be 1-{MODEL_NAME_MAX} characters: letters, digits, spaces and - _ . ( ) ·"
        )
    return name


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
            "tags": [LATEST_TAG],
            "created_at": now,
        }
        await self._db.model_versions.update_many(
            {**scope, "model_id": model_id, "tags": LATEST_TAG}, {"$pull": {"tags": LATEST_TAG}}
        )
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
            self._db.models.find({"org_id": org_id, "user_id": user_id, "archived_at": None}, MODEL_PROJECTION)
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def get_model(self, *, org_id: str, user_id: str, model_id: str) -> dict[str, Any] | None:
        return await self._db.models.find_one(
            {"org_id": org_id, "user_id": user_id, "id": model_id, "archived_at": None}, MODEL_PROJECTION
        )

    async def list_versions(self, *, org_id: str, user_id: str, model_id: str) -> list[dict[str, Any]]:
        scope = {"org_id": org_id, "user_id": user_id, "model_id": model_id}
        await self._ensure_latest(scope)
        cursor = self._db.model_versions.find(
            {**scope, "archived_at": None}, VERSION_PROJECTION
        ).sort("version", DESCENDING)
        return [doc async for doc in cursor]

    async def set_tag(
        self, *, org_id: str, user_id: str, model_id: str, version: int, tag: str, actor_email: str | None
    ) -> None:
        if not TAG_RE.fullmatch(tag):
            raise InvalidTag("tags are 1-32 characters: lowercase letters, digits, '-' or '_', starting with a letter")
        scope = {"org_id": org_id, "user_id": user_id, "model_id": model_id}
        target = await self._db.model_versions.find_one({**scope, "version": version, "archived_at": None}, {"_id": 1})
        if target is None:
            raise LookupError(f"version {version} not found")
        await self._db.model_versions.update_many({**scope, "tags": tag}, {"$pull": {"tags": tag}})
        await self._db.model_versions.update_one({**scope, "version": version}, {"$addToSet": {"tags": tag}})
        await self.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action="tag_set",
            version=version, actor_email=actor_email, detail=f"{tag} set to v{version}",
        )

    async def _ensure_latest(self, scope: dict[str, str]) -> None:
        live_filter = {**scope, "archived_at": None}
        if await self._db.model_versions.find_one({**live_filter, "tags": LATEST_TAG}, {"_id": 1}) is not None:
            return
        newest = await self._db.model_versions.find_one(live_filter, {"version": 1}, sort=[("version", DESCENDING)])
        if newest is not None:
            await self._db.model_versions.update_one(
                {**scope, "version": newest["version"]}, {"$addToSet": {"tags": LATEST_TAG}}
            )

    async def get_version(self, *, org_id: str, user_id: str, model_id: str, version: int) -> dict[str, Any] | None:
        return await self._db.model_versions.find_one(
            {
                "org_id": org_id, "user_id": user_id, "model_id": model_id,
                "version": version, "archived_at": None,
            },
            VERSION_PROJECTION,
        )

    async def name_taken(self, *, org_id: str, user_id: str, name: str, exclude_model_id: str | None = None) -> bool:
        query: dict[str, Any] = {
            "org_id": org_id,
            "user_id": user_id,
            "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
        }
        if exclude_model_id:
            query["id"] = {"$ne": exclude_model_id}
        return await self._db.models.find_one(query, {"_id": 1}) is not None

    async def suggest_names(self, *, org_id: str, user_id: str, base: str, count: int = 3) -> list[str]:
        stem = base[: MODEL_NAME_MAX - (1 + 2 * NAME_SUFFIX_BYTES)].rstrip()
        suggestions: list[str] = []
        for _ in range(count * 5):
            if len(suggestions) >= count:
                break
            candidate = f"{stem}-{secrets.token_hex(NAME_SUFFIX_BYTES)}"
            if await self.name_taken(org_id=org_id, user_id=user_id, name=candidate):
                continue
            suggestions.append(candidate)
        return suggestions

    async def archive_versions(
        self, *, org_id: str, user_id: str, model_id: str, versions: list[int], actor_email: str | None
    ) -> None:
        now = _now()
        scope = {"org_id": org_id, "user_id": user_id, "model_id": model_id}
        await self._db.model_versions.update_many(
            {**scope, "version": {"$in": versions}},
            {"$set": {"archived_at": now, "purge_at": now + ARCHIVE_RETENTION}},
        )
        await self._refresh_model(scope, now)
        label = ", ".join(f"v{v}" for v in sorted(versions))
        await self.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action="versions_archived",
            version=None, actor_email=actor_email,
            detail=f"{label} deallocated and archived, purged after 7 days",
        )

    async def due_purge(self, *, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self._db.model_versions.find(
            {"purge_at": {"$lte": _now()}},
            {"_id": 0, "org_id": 1, "user_id": 1, "model_id": 1, "version": 1, "job_id": 1},
        ).limit(limit)
        return [doc async for doc in cursor]

    async def _refresh_model(self, scope: dict[str, str], now: datetime) -> None:
        live_filter = {**scope, "archived_at": None}
        live = await self._db.model_versions.find_one(live_filter, {"version": 1}, sort=[("version", DESCENDING)])
        await self._ensure_latest(scope)
        count = await self._db.model_versions.count_documents(live_filter)
        await self._db.models.update_one(
            {"org_id": scope["org_id"], "user_id": scope["user_id"], "id": scope["model_id"]},
            {
                "$set": {
                    "latest_version": live["version"] if live else 0,
                    "version_count": count,
                    "updated_at": now,
                    "archived_at": None if live else now,
                }
            },
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

    async def live_deployments(
        self, *, org_id: str, user_id: str, model_id: str, versions: list[int]
    ) -> list[dict[str, Any]]:
        cursor = self._db.deployments.find(
            {
                "org_id": org_id,
                "user_id": user_id,
                "model_id": model_id,
                "version": {"$in": versions},
                "status": {"$in": list(ACTIVE_DEPLOYMENT_STATUSES)},
            },
            {"_id": 0, "id": 1, "version": 1, "status": 1},
        )
        return [doc async for doc in cursor]

    async def delete_version(
        self, *, org_id: str, user_id: str, model_id: str, version: int, actor_email: str | None
    ) -> None:
        scope = {"org_id": org_id, "user_id": user_id, "model_id": model_id}
        await self._db.model_versions.delete_one({**scope, "version": version})
        await self.record_event(
            org_id=org_id, user_id=user_id, model_id=model_id, action="version_deleted",
            version=version, actor_email=actor_email, detail=f"v{version} removed with its training job",
        )
        remaining = await self._db.model_versions.find_one(scope, {"version": 1})
        if remaining is None:
            await self._db.models.delete_one({"org_id": org_id, "user_id": user_id, "id": model_id})
            await self._db.model_events.delete_many(scope)
            return
        await self._refresh_model(scope, _now())
