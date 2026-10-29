import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from agent.request_context import parse_client_timezone
from agent.runtime import pending_approval, stream_turn
from agent.tools.system_ops.hitl.ask_user import check_answer
from integrations.auth.dependencies import Principal, get_principal
from integrations.keyvault.client import KeyVaultError
from integrations.training.scope import JobScope

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)

LIST_LIMIT = 50
DEFAULT_TITLE = "New chat"
TITLE_MAX = 60
MESSAGE_MAX = 8000
MAX_DECISIONS = 20


class ChatSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: str | None = None
    created_at: datetime


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=MESSAGE_MAX)


class PendingAction(BaseModel):
    name: str
    args: dict[str, Any]
    description: str = ""
    allowed_decisions: list[str]


class PendingApproval(BaseModel):
    interrupt_id: str
    actions: list[PendingAction]


class EditedAction(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    args: dict[str, Any]


class DecisionIn(BaseModel):
    type: Literal["approve", "edit", "reject", "respond"]
    message: str | None = Field(default=None, max_length=MESSAGE_MAX)
    value: Any | None = None
    edited_action: EditedAction | None = None

    @model_validator(mode="after")
    def _required_fields(self) -> "DecisionIn":
        if self.type == "edit" and self.edited_action is None:
            raise ValueError("edit requires edited_action")
        if self.type == "respond" and self.value is None and not (self.message or "").strip():
            raise ValueError("respond requires message or value")
        return self


class ResumeIn(BaseModel):
    decisions: list[DecisionIn] = Field(min_length=1, max_length=MAX_DECISIONS)


def _now() -> datetime:
    return datetime.now(UTC)


async def _owned_chat(request: Request, principal: Principal, chat_id: str) -> None:
    found = await request.app.state.db.chats.find_one(
        {"id": chat_id, "org_id": principal.org_id, "user_id": principal.user_id},
        {"_id": 1},
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Chat not found")


async def _get_agent(request: Request) -> Any:
    state = request.app.state
    if state.agent is None:
        async with state.agent_lock:
            if state.agent is None:
                try:
                    state.agent = await asyncio.to_thread(
                        state.agent_factory, state.settings, state.checkpointer
                    )
                except KeyVaultError as exc:
                    logger.warning("agent unavailable: %s", exc)
                    raise HTTPException(status_code=503, detail="LLM is not configured") from exc
    return state.agent


def _client_timezone(request: Request) -> str | None:
    return parse_client_timezone(request.headers.get("x-client-timezone"))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


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


@router.post("/chats", response_model=ChatSummary, status_code=201)
async def create_chat(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> ChatSummary:
    now = _now()
    doc = {
        "id": uuid.uuid4().hex,
        "org_id": principal.org_id,
        "user_id": principal.user_id,
        "title": DEFAULT_TITLE,
        "created_at": now,
        "updated_at": now,
    }
    await request.app.state.db.chats.insert_one(doc)
    return ChatSummary(**{k: doc[k] for k in ("id", "title", "created_at", "updated_at")})


@router.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> list[MessageOut]:
    await _owned_chat(request, principal, chat_id)
    cursor = (
        request.app.state.db.messages.find(
            {"org_id": principal.org_id, "user_id": principal.user_id, "chat_id": chat_id},
            {"_id": 0, "id": 1, "role": 1, "content": 1, "thinking": 1, "created_at": 1},
        )
        .sort("created_at", 1)
        .limit(LIST_LIMIT * 4)
    )
    return [MessageOut(**doc) async for doc in cursor]


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: str,
    body: MessageIn,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    await _owned_chat(request, principal, chat_id)
    active: set[str] = request.app.state.active_chats
    if chat_id in active:
        raise HTTPException(status_code=409, detail="A run is already active for this chat")
    active.add(chat_id)
    try:
        agent = await _get_agent(request)
        if await pending_approval(agent, chat_id) is not None:
            raise HTTPException(status_code=409, detail="Resolve the pending approval before sending a message")
        db = request.app.state.db
        owner = {"org_id": principal.org_id, "user_id": principal.user_id}
        scope = {**owner, "chat_id": chat_id}
        now = _now()
        await db.messages.insert_one(
            {"id": uuid.uuid4().hex, **scope, "role": "user", "content": body.content, "created_at": now}
        )
        chat = await db.chats.find_one({"id": chat_id, **owner}, {"title": 1})
        update: dict[str, Any] = {"updated_at": now}
        if chat and chat.get("title") == DEFAULT_TITLE:
            update["title"] = body.content.strip()[:TITLE_MAX]
        await db.chats.update_one({"id": chat_id, **owner}, {"$set": update})
    except BaseException:
        active.discard(chat_id)
        raise

    return _stream_response(request, scope, agent, content=body.content, timezone=_client_timezone(request))


@router.get("/chats/{chat_id}/pending", response_model=PendingApproval | None)
async def get_pending(
    chat_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> PendingApproval | None:
    await _owned_chat(request, principal, chat_id)
    agent = await _get_agent(request)
    return await pending_approval(agent, chat_id)


@router.post("/chats/{chat_id}/resume")
async def resume_chat(
    chat_id: str,
    body: ResumeIn,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    await _owned_chat(request, principal, chat_id)
    active: set[str] = request.app.state.active_chats
    if chat_id in active:
        raise HTTPException(status_code=409, detail="A run is already active for this chat")
    active.add(chat_id)
    try:
        agent = await _get_agent(request)
        pending = await pending_approval(agent, chat_id)
        if pending is None:
            raise HTTPException(status_code=409, detail="No pending approval for this chat")
        decisions = _check_decisions(pending, body.decisions)
    except BaseException:
        active.discard(chat_id)
        raise

    scope = {"org_id": principal.org_id, "user_id": principal.user_id, "chat_id": chat_id}
    return _stream_response(request, scope, agent, decisions=decisions, timezone=_client_timezone(request))


def _check_decisions(pending: dict, decisions: list[DecisionIn]) -> list[dict]:
    actions = pending["actions"]
    if len(decisions) != len(actions):
        raise HTTPException(status_code=422, detail=f"Expected {len(actions)} decision(s), got {len(decisions)}")
    normalized: list[dict] = []
    for action, decision in zip(actions, decisions, strict=True):
        if decision.type not in action["allowed_decisions"]:
            raise HTTPException(status_code=422, detail=f"'{decision.type}' is not allowed for {action['name']}")
        if decision.type == "edit" and decision.edited_action.name != action["name"]:
            raise HTTPException(status_code=422, detail="edited_action.name must match the pending action")
        if decision.type == "respond" and action["name"] == "ask_user":
            normalized.append({"type": "respond", "message": _typed_answer(action, decision)})
        else:
            normalized.append(decision.model_dump(exclude_none=True))
    return normalized


def _typed_answer(action: dict, decision: DecisionIn) -> str:
    raw = decision.value if decision.value is not None else decision.message
    try:
        return check_answer(action["args"], raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def split_reply(text: str, boundary: int) -> tuple[str, str]:
    """Text before the last tool event is process (thinking); the rest is the answer."""
    return text[:boundary].rstrip(), text[boundary:].lstrip()


def _stream_response(
    request: Request,
    scope: dict[str, str],
    agent: Any,
    **turn: Any,
) -> StreamingResponse:
    db = request.app.state.db
    active: set[str] = request.app.state.active_chats
    chat_id = scope["chat_id"]
    job_scope = JobScope(
        service=request.app.state.training,
        org_id=scope["org_id"],
        user_id=scope["user_id"],
        chat_id=chat_id,
    )

    async def events() -> AsyncIterator[str]:
        reply: list[str] = []
        boundary = 0
        paused = False
        try:
            async for event, data in stream_turn(agent, chat_id, job_scope=job_scope, **turn):
                if event == "token":
                    reply.append(data["text"])
                if event in ("tool_call", "tool_result"):
                    boundary = len("".join(reply))
                if event == "interrupt":
                    paused = True
                    boundary = len("".join(reply))
                yield _sse(event, data)
            text = "".join(reply)
            thinking, content = split_reply(text, boundary)
            if text:
                await db.messages.insert_one(
                    {
                        "id": uuid.uuid4().hex,
                        **scope,
                        "role": "assistant",
                        "content": content,
                        "thinking": thinking,
                        "created_at": _now(),
                    }
                )
            if not paused:
                yield _sse("done", {"chat_id": chat_id})
        except Exception:
            logger.exception("agent turn failed for chat %s", chat_id)
            yield _sse("error", {"message": "The agent run failed. Please try again."})
        finally:
            active.discard(chat_id)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
