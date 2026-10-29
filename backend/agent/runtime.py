import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.types import Command

from config.settings import Settings
from integrations.keyvault.client import build_keyvault_reader
from integrations.llm.foundry import build_claude_model
from integrations.training.scope import JobScope, bind_scope
from agent.components.todos import TODO_TOOL, todos_from_args
from agent.factory import build_dana_agent

logger = logging.getLogger(__name__)


def build_default_agent(settings: Settings, checkpointer: Any):
    reader = build_keyvault_reader(settings)
    try:
        model = build_claude_model(reader, settings.llm_model)
    finally:
        reader.close()
    return build_dana_agent(model, settings.agent_root, checkpointer=checkpointer)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content or []
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _config(chat_id: str) -> dict:
    return {"configurable": {"thread_id": chat_id}}


def approval_payload(interrupt: Any) -> dict:
    value = interrupt.value
    allowed = {review["action_name"]: review["allowed_decisions"] for review in value["review_configs"]}
    actions = [
        {
            "name": action["name"],
            "args": action["args"],
            "description": action.get("description", ""),
            "allowed_decisions": allowed.get(action["name"], []),
        }
        for action in value["action_requests"]
    ]
    return {"interrupt_id": interrupt.id, "actions": actions}


async def pending_approval(agent: Any, chat_id: str) -> dict | None:
    snapshot = await agent.aget_state(_config(chat_id))
    for interrupt in snapshot.interrupts:
        return approval_payload(interrupt)
    return None


async def stream_turn(
    agent: Any,
    chat_id: str,
    *,
    content: str | None = None,
    decisions: list[dict] | None = None,
    job_scope: JobScope | None = None,
) -> AsyncIterator[tuple[str, dict]]:
    bind_scope(job_scope)
    config = _config(chat_id)
    if decisions is not None:
        payload: Any = Command(resume={"decisions": decisions})
    else:
        payload = {"messages": [{"role": "user", "content": content}]}
    async for event in agent.astream_events(payload, config=config, version="v2"):
        kind = event["event"]
        data = event.get("data") or {}
        if kind == "on_chat_model_stream":
            text = _text_of(data["chunk"].content)
            if text:
                yield "token", {"text": text}
        elif kind == "on_tool_start":
            name = event.get("name", "")
            args = data.get("input") or {}
            if name == TODO_TOOL:
                yield "todos", {"todos": todos_from_args(args)}
            yield "tool_call", {"id": str(event["run_id"]), "name": name, "args": args}
        elif kind == "on_tool_end":
            yield "tool_result", {"id": str(event["run_id"]), "name": event.get("name", "")}
    pending = await pending_approval(agent, chat_id)
    if pending is not None:
        yield "interrupt", pending
