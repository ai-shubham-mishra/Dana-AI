from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/api/v1")

LIST_LIMIT = 50
EVENT_LIMIT = 200
SUMMARY_FIELDS = {
    "_id": 0,
    "id": 1,
    "title": 1,
    "kind": 1,
    "status": 1,
    "stage": 1,
    "percent": 1,
    "message": 1,
    "error": 1,
    "created_at": 1,
    "updated_at": 1,
}


class JobSummary(BaseModel):
    id: str
    title: str
    kind: str
    status: str
    stage: str | None = None
    percent: int = 0
    message: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobArtifact(BaseModel):
    name: str
    bytes: int


class JobEvent(BaseModel):
    stage: str
    percent: int
    message: str
    created_at: datetime


class JobDetail(JobSummary):
    params: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    artifact: JobArtifact | None = None
    artifacts: list[JobArtifact] = []
    events: list[JobEvent] = []


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> list[JobSummary]:
    cursor = (
        request.app.state.db.jobs.find(
            {"org_id": principal.org_id, "user_id": principal.user_id},
            SUMMARY_FIELDS,
        )
        .sort("created_at", -1)
        .limit(LIST_LIMIT)
    )
    return [JobSummary(**doc) async for doc in cursor]


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> JobDetail:
    db = request.app.state.db
    doc = await db.jobs.find_one(
        {"id": job_id, "org_id": principal.org_id, "user_id": principal.user_id},
        {"_id": 0, "org_id": 0, "user_id": 0, "chat_id": 0},
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Job not found")
    events_cursor = (
        db.job_events.find({"job_id": job_id}, {"_id": 0, "stage": 1, "percent": 1, "message": 1, "created_at": 1})
        .sort("created_at", 1)
        .limit(EVENT_LIMIT)
    )
    events = [JobEvent(**event) async for event in events_cursor]
    files = (doc.get("artifact") or {}).get("files") or []
    artifacts = [JobArtifact(**item) for item in files if isinstance(item, dict)]
    return JobDetail(**doc, events=events, artifacts=artifacts)
