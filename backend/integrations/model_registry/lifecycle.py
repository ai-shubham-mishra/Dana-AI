import asyncio
import logging
from typing import Any

from integrations.deployments.service import DeploymentBusy, DeprovisionFailed
from integrations.training.service import ACTIVE_STATUSES as TRAINING_ACTIVE_STATUSES

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 900


class ModelLifecycle:
    def __init__(self, *, registry: Any, training: Any, deployments: Any):
        self._registry = registry
        self._training = training
        self._deployments = deployments

    async def delete_model(
        self, *, org_id: str, user_id: str, model_id: str, actor_email: str | None, deallocate: bool = False
    ) -> dict[str, Any]:
        versions = await self._registry.list_versions(org_id=org_id, user_id=user_id, model_id=model_id)
        if not versions:
            raise LookupError("Model not found")
        return await self._delete(
            org_id=org_id, user_id=user_id, model_id=model_id, versions=versions,
            actor_email=actor_email, deallocate=deallocate,
        )

    async def delete_versions(
        self,
        *,
        org_id: str,
        user_id: str,
        model_id: str,
        version_numbers: list[int],
        actor_email: str | None,
        deallocate: bool = False,
    ) -> dict[str, Any]:
        wanted = set(version_numbers)
        versions = [
            v for v in await self._registry.list_versions(org_id=org_id, user_id=user_id, model_id=model_id)
            if v["version"] in wanted
        ]
        if not versions:
            raise LookupError("Version not found")
        return await self._delete(
            org_id=org_id, user_id=user_id, model_id=model_id, versions=versions,
            actor_email=actor_email, deallocate=deallocate,
        )

    async def _delete(
        self,
        *,
        org_id: str,
        user_id: str,
        model_id: str,
        versions: list[dict[str, Any]],
        actor_email: str | None,
        deallocate: bool,
    ) -> dict[str, Any]:
        numbers = [v["version"] for v in versions]
        for version in versions:
            job = await self._training.get_job(org_id=org_id, user_id=user_id, job_id=version["job_id"])
            if job and job["status"] in TRAINING_ACTIVE_STATUSES:
                return {"outcome": "blocked", "reason": f"v{version['version']} is still training; wait for it to finish"}

        live = await self._registry.live_deployments(
            org_id=org_id, user_id=user_id, model_id=model_id, versions=numbers
        )
        if live and not deallocate:
            return {"outcome": "needs_confirmation", "deployments": live}

        stopped: list[str] = []
        for dep in live:
            try:
                await self._deployments.deallocate(
                    org_id=org_id, user_id=user_id, dep_id=dep["id"], actor_email=actor_email
                )
            except (DeploymentBusy, DeprovisionFailed) as exc:
                return {"outcome": "blocked", "reason": str(exc)}
            stopped.append(dep["id"])
        await self._registry.archive_versions(
            org_id=org_id, user_id=user_id, model_id=model_id, versions=numbers, actor_email=actor_email
        )
        return {"outcome": "archived", "versions": numbers, "deallocated": stopped}

    async def purge_due(self) -> int:
        purged = 0
        if self._deployments is not None:
            purged += await self._deployments.purge_due()
        for doc in await self._registry.due_purge():
            org_id, user_id = doc["org_id"], doc["user_id"]
            result = await self._training.delete_jobs(
                org_id=org_id, user_id=user_id, job_ids=[doc["job_id"]], actor_email=None
            )
            if result["deleted"]:
                purged += 1
                continue
            reason = result["skipped"][0]["reason"] if result["skipped"] else ""
            if reason == "Job not found":
                await self._registry.delete_version(
                    org_id=org_id, user_id=user_id, model_id=doc["model_id"],
                    version=doc["version"], actor_email=None,
                )
                purged += 1
            else:
                logger.info("Purge of model %s v%s deferred: %s", doc["model_id"], doc["version"], reason)
        return purged


async def run_purge_loop(lifecycle: ModelLifecycle, interval: float = PURGE_INTERVAL_SECONDS) -> None:
    while True:
        try:
            await lifecycle.purge_due()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Model version purge failed; will retry")
        await asyncio.sleep(interval)
