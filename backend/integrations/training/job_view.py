from datetime import datetime
from typing import Any


def kind_for_family(model_family: str | None) -> str | None:
    if not model_family or not model_family.strip():
        return None
    return f"{model_family.strip().lower()}_training"


def _when(value: datetime | None) -> str:
    return value.isoformat(timespec="minutes") if value else "unknown"


def describe_job(job: dict[str, Any]) -> str:
    lines = [
        f"Job {job['id']}: {job.get('title') or job.get('kind')}",
        f"Status: {job.get('status')} ({job.get('stage') or 'no stage'}, {job.get('percent') or 0}%)",
        f"Created: {_when(job.get('created_at'))}",
        f"Last update: {_when(job.get('updated_at'))}",
    ]
    if job.get("message"):
        lines.append(f"Message: {job['message']}")
    if job.get("error"):
        lines.append(f"Error: {job['error']}")
    return "\n".join(lines)


def describe_model(job: dict[str, Any]) -> str:
    artifact = job.get("artifact") or {}
    params = job.get("params") or {}
    lines = [
        f"Model from job {job['id']}: {job.get('title') or job.get('kind')}",
        f"Trained: {_when(job.get('updated_at'))}",
    ]
    if params.get("kpi"):
        lines.append(f"KPI: {params['kpi']}")
    if params.get("channels"):
        lines.append(f"Channels: {', '.join(params['channels'])}")
    if params.get("date_start") and params.get("date_end"):
        lines.append(f"Date range: {params['date_start']} to {params['date_end']}")
    if artifact:
        lines.append(f"Artifact: {artifact.get('name')} ({artifact.get('bytes', 0)} bytes)")
        lines.append(f"Saved at: {artifact.get('blob_container')}/{artifact.get('blob_path')}")
    if describe_metrics(job):
        lines.append(describe_metrics(job))
    return "\n".join(lines)


def describe_metrics(job: dict[str, Any]) -> str:
    metrics = job.get("metrics") or {}
    if not metrics:
        return ""
    return "\n".join(["Metrics:", *(f"  {key}: {value}" for key, value in metrics.items())])
