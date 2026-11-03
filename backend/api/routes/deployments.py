import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal
from integrations.deployments.leases import NoPortAvailable
from integrations.deployments.service import DeploymentBusy, DeprovisionFailed, VersionAlreadyDeployed

router = APIRouter(prefix="/api/v1")


class DeploymentHealth(BaseModel):
    state: str
    detail: str | None = None


class ArchivedDeployment(BaseModel):
    id: str
    model_id: str
    version: int
    status: str
    host_port: int
    container: str
    created_by_email: str | None = None
    created_at: datetime
    archived_at: datetime
    purge_at: datetime
    days_remaining: int


class Deployment(BaseModel):
    id: str
    model_id: str
    version: int
    job_id: str
    status: str
    stage: str | None = None
    percent: int = 0
    host_port: int
    url: str
    container: str
    message: str | None = None
    error: str | None = None
    created_by_email: str | None = None
    created_at: datetime
    updated_at: datetime
    health: DeploymentHealth


def _as_response(doc: dict[str, Any]) -> Deployment:
    return Deployment(**doc)


@router.post(
    "/models/{model_id}/versions/{version}/deployments",
    response_model=Deployment,
    status_code=status.HTTP_202_ACCEPTED,
)
async def allocate_deployment(
    model_id: str,
    version: int,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Deployment:
    service = request.app.state.deployments
    try:
        created = await service.allocate(
            org_id=principal.org_id,
            user_id=principal.user_id,
            model_id=model_id,
            version=version,
            actor_email=principal.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoPortAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VersionAlreadyDeployed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _as_response(
        await service.get(org_id=principal.org_id, user_id=principal.user_id, dep_id=created["id"])
    )


@router.get("/deployments", response_model=list[Deployment])
async def list_deployments(
    request: Request,
    model_id: str | None = None,
    principal: Principal = Depends(get_principal),
) -> list[Deployment]:
    docs = await request.app.state.deployments.list_deployments(
        org_id=principal.org_id, user_id=principal.user_id, model_id=model_id
    )
    return [_as_response(doc) for doc in docs]


@router.get("/deployments/archive", response_model=list[ArchivedDeployment])
async def list_archived_deployments(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> list[ArchivedDeployment]:
    docs = await request.app.state.deployments.list_archived(
        org_id=principal.org_id, user_id=principal.user_id
    )
    now = datetime.now(UTC)
    return [
        ArchivedDeployment(
            id=doc["id"],
            model_id=doc["model_id"],
            version=doc["version"],
            status=doc["status"],
            host_port=doc["host_port"],
            container=doc["container"],
            created_by_email=doc.get("created_by_email"),
            created_at=doc["created_at"],
            archived_at=doc["archived_at"],
            purge_at=doc["purge_at"],
            days_remaining=max(0, ceil((doc["purge_at"] - now).total_seconds() / 86400)),
        )
        for doc in docs
    ]


@router.get("/deployments/{dep_id}", response_model=Deployment)
async def get_deployment(
    dep_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Deployment:
    try:
        doc = await request.app.state.deployments.get(org_id=principal.org_id, user_id=principal.user_id, dep_id=dep_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _as_response(doc)


@router.post("/deployments/{dep_id}/deallocate", response_model=Deployment)
async def deallocate_deployment(
    dep_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Deployment:
    service = request.app.state.deployments
    try:
        await service.deallocate(
            org_id=principal.org_id, user_id=principal.user_id, dep_id=dep_id, actor_email=principal.email
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DeploymentBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeprovisionFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _as_response(await service.get(org_id=principal.org_id, user_id=principal.user_id, dep_id=dep_id))


@router.get("/deployments/{dep_id}/logs")
async def deployment_logs(
    dep_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    service = request.app.state.deployments
    try:
        await service.find(org_id=principal.org_id, user_id=principal.user_id, dep_id=dep_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def events() -> AsyncIterator[str]:
        async for line in service.tail_logs(dep_id):
            yield f"data: {json.dumps(line)}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
