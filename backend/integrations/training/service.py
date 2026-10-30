import asyncio
import json
import logging
import sys
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import BACKEND_ROOT, Settings
from integrations.training.mmm.dataset import build_dataset, validate_sources
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.mmm.recipe import build_config, dump_config, render_script
from integrations.training.mmm.request import (
    DatasetSpec,
    MMMRequest,
    load_dataset_spec,
    validate_request,
)
from integrations.training.mmm.run_folder import RUN_FILES, missing_outputs, write_inputs
from integrations.training.mmm.sandbox import SandboxError, run_script, sandbox_env
from integrations.training.protocol import parse_line

logger = logging.getLogger(__name__)

JOB_KIND = "mmm_training"
MMM_DATA_FILE = "mmm_demo.csv"
MMM_CONFIG_FILE = "mmm_demo.yaml"
MODEL_FILE = "mmm_model.nc"
STDERR_TAIL = 20
JOB_PROJECTION = {
    "_id": 0,
    "id": 1,
    "title": 1,
    "kind": 1,
    "status": 1,
    "stage": 1,
    "percent": 1,
    "message": 1,
    "error": 1,
    "params": 1,
    "metrics": 1,
    "artifact": 1,
    "created_at": 1,
    "updated_at": 1,
}

CommandFactory = Callable[[Path, MMMRequest], list[str]]


def _now() -> datetime:
    return datetime.now(UTC)


def _title(request: MMMRequest) -> str:
    return f"MMM training · {request.kpi} · {request.date_start} to {request.date_end}"


def _plan_title(plan: MMMPlan) -> str:
    return f"MMM training · {plan.kpi} · {plan.date_start} to {plan.date_end}"


async def _drain(stream: asyncio.StreamReader, tail: deque[str]) -> None:
    async for raw in stream:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            tail.append(line)


class TrainingService:
    def __init__(
        self,
        *,
        db: Any,
        blob: Any,
        settings: Settings,
        command_factory: CommandFactory | None = None,
        connector_pool: Any | None = None,
        datasets_schema: str = "datasets",
    ):
        self._db = db
        self._blob = blob
        self._settings = settings
        self._data_path = settings.training_mmm_dir / MMM_DATA_FILE
        self._config_path = settings.training_mmm_dir / MMM_CONFIG_FILE
        self._spec: DatasetSpec = load_dataset_spec(self._config_path)
        self._command_factory = command_factory or self._mmm_command
        self._connector_pool = connector_pool
        self._datasets_schema = datasets_schema
        self._slots = asyncio.Semaphore(1)
        self._tasks: set[asyncio.Task] = set()

    async def submit_mmm_plan(self, *, org_id: str, user_id: str, chat_id: str, plan: MMMPlan) -> str:
        if self._connector_pool is None:
            raise PlanError("connector data is not configured for training")
        await validate_sources(self._connector_pool, self._datasets_schema, plan)
        job_id = uuid.uuid4().hex
        now = _now()
        await self._db.jobs.insert_one(
            {
                "id": job_id,
                "org_id": org_id,
                "user_id": user_id,
                "chat_id": chat_id,
                "title": _plan_title(plan),
                "kind": JOB_KIND,
                "status": "queued",
                "stage": "queued",
                "percent": 0,
                "message": "Waiting for a free training slot",
                "error": None,
                "params": plan.to_dict(),
                "metrics": None,
                "artifact": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await self._event(job_id, org_id, user_id, "queued", 0, "Waiting for a free training slot")
        task = asyncio.create_task(self._run_plan(job_id, org_id, user_id, plan))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def submit(
        self,
        *,
        org_id: str,
        user_id: str,
        chat_id: str,
        model: str,
        kpi: str,
        channels: list[str],
        date_range: str,
    ) -> str:
        request = validate_request(
            model=model, kpi=kpi, channels=channels, date_range=date_range, spec=self._spec
        )
        job_id = uuid.uuid4().hex
        now = _now()
        await self._db.jobs.insert_one(
            {
                "id": job_id,
                "org_id": org_id,
                "user_id": user_id,
                "chat_id": chat_id,
                "title": _title(request),
                "kind": JOB_KIND,
                "status": "queued",
                "stage": "queued",
                "percent": 0,
                "message": "Waiting for a free training slot",
                "error": None,
                "params": request.to_dict(),
                "metrics": None,
                "artifact": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await self._event(job_id, org_id, user_id, "queued", 0, "Waiting for a free training slot")
        task = asyncio.create_task(self._run(job_id, org_id, user_id, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def get_job(self, *, org_id: str, user_id: str, job_id: str) -> dict[str, Any] | None:
        return await self._db.jobs.find_one(
            {"id": job_id, "org_id": org_id, "user_id": user_id}, JOB_PROJECTION
        )

    async def find_latest_job(
        self,
        *,
        org_id: str,
        user_id: str,
        kind: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {"org_id": org_id, "user_id": user_id}
        if kind:
            query["kind"] = kind
        if statuses:
            query["status"] = {"$in": list(statuses)}
        return await self._db.jobs.find_one(query, JOB_PROJECTION, sort=[("created_at", -1)])

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _mmm_command(self, job_dir: Path, request: MMMRequest) -> list[str]:
        return [
            sys.executable,
            "-m",
            "integrations.training.mmm.cli",
            "--data",
            str(self._data_path),
            "--config",
            str(self._config_path),
            "--output-dir",
            str(job_dir),
            "--request",
            json.dumps(request.to_dict()),
        ]

    async def _run(self, job_id: str, org_id: str, user_id: str, request: MMMRequest) -> None:
        async with self._slots:
            proc: asyncio.subprocess.Process | None = None
            try:
                await self._update(job_id, status="running", stage="starting", percent=1,
                                   message="Starting the trainer")
                job_dir = self._settings.training_output_dir / job_id
                proc = await asyncio.create_subprocess_exec(
                    *self._command_factory(job_dir, request),
                    cwd=str(BACKEND_ROOT),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                tail: deque[str] = deque(maxlen=STDERR_TAIL)
                drain = asyncio.create_task(_drain(proc.stderr, tail))
                result: dict[str, Any] | None = None
                async for raw in proc.stdout:
                    parsed = parse_line(raw.decode("utf-8", "replace").rstrip())
                    if parsed is None:
                        continue
                    kind, payload = parsed
                    if kind == "progress":
                        await self._progress(job_id, org_id, user_id, payload)
                    else:
                        result = payload
                code = await proc.wait()
                await drain
                if code == 0 and result and result.get("status") == "success":
                    await self._finish(job_id, org_id, user_id, result)
                else:
                    message = (result or {}).get("message") or (tail[-1] if tail else "") \
                        or f"trainer exited with code {code}"
                    await self._fail(job_id, org_id, user_id, message)
            except asyncio.CancelledError:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                try:
                    await self._fail(job_id, org_id, user_id, "Training was interrupted by a server shutdown")
                except Exception:
                    logger.exception("could not record interrupted training job %s", job_id)
                raise
            except Exception as exc:
                logger.exception("training job %s crashed", job_id)
                await self._fail(job_id, org_id, user_id, f"Training failed: {type(exc).__name__}")

    async def _run_plan(self, job_id: str, org_id: str, user_id: str, plan: MMMPlan) -> None:
        async with self._slots:
            try:
                await self._update(job_id, status="running", stage="compiling_data", percent=2,
                                   message="Compiling the dataset from connector tables")
                dataset = await build_dataset(self._connector_pool, self._datasets_schema, org_id, plan)
                config = build_config(plan)
                script = render_script(config, plan.to_dict(), _now().isoformat())
                run_dir = self._settings.training_output_dir / job_id
                write_inputs(run_dir, dataset.columns, dataset.rows, dump_config(config), script)
                message = f"Run folder ready with {len(dataset.rows)} rows and the generated training script"
                await self._progress(job_id, org_id, user_id,
                                     {"stage": "run_folder", "percent": 5, "message": message})

                async def on_progress(payload: dict[str, Any]) -> None:
                    await self._progress(job_id, org_id, user_id, payload)

                outcome = await run_script(
                    [sys.executable, str(run_dir / "train.py")],
                    run_dir,
                    on_progress,
                    env=sandbox_env(),
                )
                result = outcome.result or {}
                if outcome.code != 0 or result.get("status") != "success":
                    message = result.get("message") or (outcome.tail[-1] if outcome.tail else "") \
                        or f"training script exited with code {outcome.code}"
                    await self._fail(job_id, org_id, user_id, message)
                    return
                missing = missing_outputs(run_dir)
                if missing:
                    await self._fail(job_id, org_id, user_id,
                                     f"run folder is missing: {', '.join(missing)}")
                    return
                result = {**result, "model_path": str(run_dir / MODEL_FILE)}
                await self._finish(job_id, org_id, user_id, result, extra={
                    "run_dir": str(run_dir),
                    "files": list(RUN_FILES),
                })
            except asyncio.CancelledError:
                try:
                    await self._fail(job_id, org_id, user_id, "Training was interrupted by a server shutdown")
                except Exception:
                    logger.exception("could not record interrupted training job %s", job_id)
                raise
            except (PlanError, SandboxError) as exc:
                await self._fail(job_id, org_id, user_id, str(exc))
            except Exception as exc:
                logger.exception("training job %s crashed", job_id)
                await self._fail(job_id, org_id, user_id, f"Training failed: {type(exc).__name__}")

    async def _progress(self, job_id: str, org_id: str, user_id: str, payload: dict[str, Any]) -> None:
        stage = str(payload.get("stage", "running"))
        percent = int(payload.get("percent", 0))
        message = str(payload.get("message", ""))
        await self._update(job_id, stage=stage, percent=percent, message=message)
        await self._event(job_id, org_id, user_id, stage, percent, message)

    async def _finish(
        self,
        job_id: str,
        org_id: str,
        user_id: str,
        result: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> None:
        await self._update(job_id, stage="uploading_artifact", percent=97,
                           message="Uploading the model artifact")
        await self._event(job_id, org_id, user_id, "uploading_artifact", 97, "Uploading the model artifact")
        data = await asyncio.to_thread(Path(result["model_path"]).read_bytes)
        blob_path = f"models/{org_id}/{user_id}/{job_id}/{MODEL_FILE}"
        container = self._blob.get_container_client(self._settings.blob_container)
        await container.upload_blob(name=blob_path, data=data, overwrite=True)
        artifact = {
            "name": MODEL_FILE,
            "blob_container": self._settings.blob_container,
            "blob_path": blob_path,
            "bytes": len(data),
            **(extra or {}),
        }
        message = "Model trained and saved"
        await self._update(job_id, status="succeeded", stage="done", percent=100, message=message,
                           error=None, metrics=result.get("metrics"), artifact=artifact)
        await self._event(job_id, org_id, user_id, "done", 100, message)

    async def _fail(self, job_id: str, org_id: str, user_id: str, message: str) -> None:
        await self._update(job_id, status="failed", stage="failed", message="Training failed", error=message)
        await self._event(job_id, org_id, user_id, "failed", 0, message)

    async def _update(self, job_id: str, **fields: Any) -> None:
        await self._db.jobs.update_one({"id": job_id}, {"$set": {**fields, "updated_at": _now()}})

    async def _event(self, job_id: str, org_id: str, user_id: str, stage: str, percent: int, message: str) -> None:
        await self._db.job_events.insert_one(
            {
                "job_id": job_id,
                "org_id": org_id,
                "user_id": user_id,
                "stage": stage,
                "percent": percent,
                "message": message,
                "created_at": _now(),
            }
        )
