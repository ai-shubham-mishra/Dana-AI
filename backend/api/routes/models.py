from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from integrations.auth.dependencies import Principal, get_principal
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


@router.get("/models", response_model=list[ModelSummary])
async def list_models(request: Request, principal: Principal = Depends(get_principal)) -> list[ModelSummary]:
    docs = await request.app.state.model_registry.list_models(org_id=principal.org_id, user_id=principal.user_id)
    return [ModelSummary(**doc) for doc in docs]


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
