import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal
from integrations.deployments.leases import NoPortAvailable
from integrations.deployments.service import DeploymentBusy

router = APIRouter(prefix="/api/v1")


class DeploymentHealth(BaseModel):
    state: str
    detail: str | None = None


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
