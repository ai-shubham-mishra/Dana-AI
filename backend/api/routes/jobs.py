from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/api/v1")

LIST_LIMIT = 50


class JobSummary(BaseModel):
    id: str
    title: str
    kind: str
    status: str
    created_at: datetime
    updated_at: datetime


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> list[JobSummary]:
    cursor = (
        request.app.state.db.jobs.find(
            {"org_id": principal.org_id, "user_id": principal.user_id},
            {"_id": 0, "org_id": 0, "user_id": 0},
        )
        .sort("created_at", -1)
        .limit(LIST_LIMIT)
    )
    return [JobSummary(**doc) async for doc in cursor]
