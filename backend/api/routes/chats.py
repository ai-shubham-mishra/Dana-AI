from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal

router = APIRouter(prefix="/api/v1")

LIST_LIMIT = 50


class ChatSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


@router.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> list[ChatSummary]:
    cursor = (
        request.app.state.db.chats.find(
            {"org_id": principal.org_id, "user_id": principal.user_id},
            {"_id": 0, "org_id": 0, "user_id": 0},
        )
        .sort("updated_at", -1)
        .limit(LIST_LIMIT)
    )
    return [ChatSummary(**doc) async for doc in cursor]
