from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ValidationError
from integrations.auth.dependencies import Principal, get_principal
from integrations.model_registry.archive_export import archive_filename, build_model_archive
from integrations.model_registry.registry import InvalidTag, ModelNameTaken
from integrations.training.mmm.plan import PlanError

router = APIRouter(prefix="/api/v1")


class ModelSummary(BaseModel):
    id: str
    name: str
    latest_version: int
    version_count: int
    created_at: datetime
    updated_at: datetime


class ModelVersion(BaseModel):
    model_id: str
    version: int
    job_id: str
    source: str
    source_version: int | None = None
    kpi: str | None = None
    params: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    created_by_email: str | None = None
    tags: list[str] = []
    created_at: datetime


class ModelEvent(BaseModel):
    action: str
    version: int | None = None
    actor_email: str | None = None
    detail: str | None = None
    created_at: datetime


class ModelDetail(ModelSummary):
    versions: list[ModelVersion]
    events: list[ModelEvent]


class RetrainResult(BaseModel):
    job_id: str


class ArchivedVersion(ModelVersion):
    purge_at: datetime | None = None


class ArchivedModel(BaseModel):
    id: str
    name: str
    latest_version: int
    version_count: int
    archived_at: datetime
    purge_at: datetime | None = None
    versions: list[ArchivedVersion]


def _archived_model(doc: dict[str, Any]) -> ArchivedModel:
    versions = [ArchivedVersion(**version) for version in doc["versions"]]
    purges = [version.purge_at for version in versions if version.purge_at is not None]
    return ArchivedModel(
        id=doc["id"],
        name=doc["name"],
        latest_version=max((version.version for version in versions), default=0),
        version_count=len(versions),
        archived_at=doc["archived_at"],
        purge_at=min(purges) if purges else None,
        versions=versions,
    )


@router.get("/models", response_model=list[ModelSummary])
async def list_models(request: Request, principal: Principal = Depends(get_principal)) -> list[ModelSummary]:
    docs = await request.app.state.model_registry.list_models(org_id=principal.org_id, user_id=principal.user_id)
    return [ModelSummary(**doc) for doc in docs]


@router.get("/models/archive", response_model=list[ArchivedModel])
async def list_archived_models(request: Request, principal: Principal = Depends(get_principal)) -> list[ArchivedModel]:
    docs = await request.app.state.model_registry.list_archived_models(
        org_id=principal.org_id, user_id=principal.user_id
    )
    return [_archived_model(doc) for doc in docs]


@router.get("/models/{model_id}/download")
async def download_archived_model(
    model_id: str, request: Request, principal: Principal = Depends(get_principal)
) -> Response:
    model = await request.app.state.model_registry.get_archived_model(
        org_id=principal.org_id, user_id=principal.user_id, model_id=model_id
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Archived model not found")
    training = request.app.state.training

    async def read_model_file(job_id: str) -> tuple[str, bytes] | None:
        return await training.read_model_file(org_id=principal.org_id, user_id=principal.user_id, job_id=job_id)

    data = await build_model_archive(model=model, read_model_file=read_model_file)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_filename(model["name"])}"'},
    )


@router.post("/models/{model_id}/restore", response_model=ModelDetail)
async def restore_model(model_id: str, request: Request, principal: Principal = Depends(get_principal)) -> ModelDetail:
    try:
        await request.app.state.model_registry.restore_model(
            org_id=principal.org_id, user_id=principal.user_id, model_id=model_id, actor_email=principal.email
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelNameTaken as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "name_taken", "name": exc.name, "suggestions": exc.suggestions},
        ) from exc
    return await get_model(model_id, request, principal)


@router.get("/models/{model_id}", response_model=ModelDetail)
async def get_model(model_id: str, request: Request, principal: Principal = Depends(get_principal)) -> ModelDetail:
    registry = request.app.state.model_registry
    scope = {"org_id": principal.org_id, "user_id": principal.user_id, "model_id": model_id}
    model = await registry.get_model(org_id=principal.org_id, user_id=principal.user_id, model_id=model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    versions = await registry.list_versions(**scope)
    events = await registry.list_events(**scope)
    return ModelDetail(
        **model,
        versions=[ModelVersion(**doc) for doc in versions],
        events=[ModelEvent(**doc) for doc in events],
    )


@router.post(
    "/models/{model_id}/versions/{version}/retrain",
    response_model=RetrainResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retrain_version(
    model_id: str,
    version: int,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> RetrainResult:
    try:
        job_id = await request.app.state.training.retrain_version(
            org_id=principal.org_id,
            user_id=principal.user_id,
            chat_id="",
            model_id=model_id,
            version=version,
            actor_email=principal.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors(include_url=False)) from exc
    return RetrainResult(job_id=job_id)


def _delete_outcome(result: dict[str, Any]) -> dict[str, Any]:
    outcome = result["outcome"]
    if outcome == "needs_confirmation":
        raise HTTPException(
            status_code=409,
            detail={"code": "needs_confirmation", "deployments": result["deployments"]},
        )
    if outcome == "blocked":
        raise HTTPException(
            status_code=409,
            detail={"code": "blocked", "reason": result["reason"], "deleted": result.get("deleted", [])},
        )
    return result


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    request: Request,
    deallocate: bool = False,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        result = await request.app.state.model_lifecycle.delete_model(
            org_id=principal.org_id,
            user_id=principal.user_id,
            model_id=model_id,
            actor_email=principal.email,
            deallocate=deallocate,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _delete_outcome(result)


@router.delete("/models/{model_id}/versions/{version}")
async def delete_version(
    model_id: str,
    version: int,
    request: Request,
    deallocate: bool = False,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        result = await request.app.state.model_lifecycle.delete_versions(
            org_id=principal.org_id,
            user_id=principal.user_id,
            model_id=model_id,
            version_numbers=[version],
            actor_email=principal.email,
            deallocate=deallocate,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _delete_outcome(result)


@router.put("/models/{model_id}/versions/{version}/tags/{tag}", response_model=ModelDetail)
async def set_version_tag(
    model_id: str,
    version: int,
    tag: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> ModelDetail:
    try:
        await request.app.state.model_registry.set_tag(
            org_id=principal.org_id,
            user_id=principal.user_id,
            model_id=model_id,
            version=version,
            tag=tag,
            actor_email=principal.email,
        )
    except InvalidTag as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await get_model(model_id, request, principal)
