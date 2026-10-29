from fastapi import APIRouter, Depends
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/api/v1")


class MeResponse(BaseModel):
    user_id: str
    org_id: str
    email: str | None
    role: str


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        org_id=principal.org_id,
        email=principal.email,
        role=principal.role,
    )
