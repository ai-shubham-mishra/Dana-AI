from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

from integrations.auth.dependencies import Principal, get_principal
from integrations.model_registry.registry import InvalidModelName, ModelNameTaken
from integrations.plans.markdown import InvalidPlan
from integrations.plans.store import PlanNameTaken, plan_slug
from integrations.training.mmm.plan import MMMPlan, PlanError

router = APIRouter(prefix="/api/v1")


class PlanCreate(BaseModel):
    name: str
    description: str = ""
    visibility: str = "private"
    content: str


class PlanPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    content: str | None = None


class PlanRunRequest(BaseModel):
    model_name: str


class PlanOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    visibility: str
    content: str
    spec: dict[str, Any]
    owner_id: str
    owner_email: str | None = None
    is_owner: bool
    created_at: datetime
    updated_at: datetime


class PlanRunOut(BaseModel):
    job_id: str


def _plan_out(doc: dict[str, Any], principal: Principal) -> PlanOut:
    return PlanOut(**{**doc, "slug": plan_slug(doc)}, is_owner=doc["owner_id"] == principal.user_id)


def _name_conflict(exc: PlanNameTaken) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(request: Request, principal: Principal = Depends(get_principal)) -> list[PlanOut]:
    docs = await request.app.state.plans.list_visible(org_id=principal.org_id, user_id=principal.user_id)
    return [_plan_out(doc, principal) for doc in docs]


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(body: PlanCreate, request: Request, principal: Principal = Depends(get_principal)) -> PlanOut:
    try:
        doc = await request.app.state.plans.create(
            org_id=principal.org_id,
            user_id=principal.user_id,
            owner_email=principal.email,
            name=body.name,
            description=body.description,
            visibility=body.visibility,
            content=body.content,
        )
    except PlanNameTaken as exc:
        raise _name_conflict(exc) from exc
    except InvalidPlan as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _plan_out(doc, principal)


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_plan(plan_id: str, request: Request, principal: Principal = Depends(get_principal)) -> PlanOut:
    doc = await request.app.state.plans.get_visible(org_id=principal.org_id, user_id=principal.user_id, plan_id=plan_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_out(doc, principal)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: str, body: PlanPatch, request: Request, principal: Principal = Depends(get_principal)
) -> PlanOut:
    changes = body.model_dump(exclude_unset=True)
    try:
        doc = await request.app.state.plans.update(
            org_id=principal.org_id, user_id=principal.user_id, plan_id=plan_id, changes=changes
        )
    except PlanNameTaken as exc:
        raise _name_conflict(exc) from exc
    except InvalidPlan as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if doc is None:
        raise HTTPException(status_code=404, detail="Plan not found or not owned by you")
    return _plan_out(doc, principal)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: str, request: Request, principal: Principal = Depends(get_principal)) -> None:
    deleted = await request.app.state.plans.delete(
        org_id=principal.org_id, user_id=principal.user_id, plan_id=plan_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found or not owned by you")


@router.post("/plans/{plan_id}/runs", response_model=PlanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def run_plan(
    plan_id: str, body: PlanRunRequest, request: Request, principal: Principal = Depends(get_principal)
) -> PlanRunOut:
    """Starts training a brand-new model from the plan. A plan never adds versions to an existing model."""
    doc = await request.app.state.plans.get_visible(org_id=principal.org_id, user_id=principal.user_id, plan_id=plan_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        plan = MMMPlan(**doc["spec"]).anchored_to(date.today())
    except (ValidationError, PlanError) as exc:
        raise HTTPException(status_code=422, detail=f"the saved plan is invalid: {exc}") from exc
    try:
        job_id = await request.app.state.training.submit_mmm_plan(
            org_id=principal.org_id,
            user_id=principal.user_id,
            chat_id="",
            plan=plan,
            model_name=body.model_name,
            source="train",
            actor_email=principal.email,
        )
    except ModelNameTaken as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "name_taken", "name": exc.name, "suggestions": exc.suggestions},
        ) from exc
    except InvalidModelName as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlanRunOut(job_id=job_id)
