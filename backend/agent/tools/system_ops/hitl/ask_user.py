import json
import math
from typing import Any, Literal

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput

ResponseType = Literal["single_select", "multi_select", "text", "number", "boolean"]
SELECT_TYPES = ("single_select", "multi_select")
MAX_OPTIONS = 50
MAX_TEXT = 2000


class AskUserInput(ToolInput):
    question: str = Field(description="One specific question for the user, for example 'Which connector holds the sales data?'.")
    response_type: ResponseType = Field(
        default="text",
        description=(
            "How the user answers. 'single_select' picks one option, 'multi_select' picks several, "
            "'text' is free text, 'number' is a numeric value, 'boolean' is yes or no."
        ),
    )
    options: list[str] | None = Field(
        default=None,
        description="Choices for single_select or multi_select (2-50 items). For text, options are optional suggestions.",
    )


def effective_type(args: dict[str, Any]) -> str:
    """A select type without options cannot be answered, so it falls back to text."""
    response_type = args.get("response_type") or "text"
    if response_type in SELECT_TYPES and not args.get("options"):
        return "text"
    return response_type


def check_answer(args: dict[str, Any], value: Any) -> str:
    """Validate a user's answer for an ask_user call and return the message the agent receives."""
    response_type = effective_type(args)
    options = [str(option) for option in (args.get("options") or [])]
    if response_type == "text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Answer with a non-empty text.")
        if len(value) > MAX_TEXT:
            raise ValueError(f"Answer must be at most {MAX_TEXT} characters.")
        return value.strip()
    if response_type == "single_select":
        if not isinstance(value, str) or value not in options:
            raise ValueError("Pick one of the offered options.")
        return json.dumps({"answer": value})
    if response_type == "multi_select":
        if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
            raise ValueError("Pick at least one of the offered options.")
        if len(set(value)) != len(value) or any(v not in options for v in value):
            raise ValueError("Pick only offered options, without duplicates.")
        return json.dumps({"answer": value})
    if response_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Answer with a finite number.")
        return json.dumps({"answer": value})
    if not isinstance(value, bool):
        raise ValueError("Answer true or false.")
    return json.dumps({"answer": value})


class AskUserTool(BaseTool):
    name: str = "ask_user"
    description: str = (
        "Ask the user a clarifying question when information needed to proceed is missing. "
        "Set response_type to match the answer: single_select or multi_select with options for known sets, "
        "number, boolean, or text. The user's answer is returned as this tool's result, as JSON for typed answers."
    )
    allowed_decisions = ["respond"]
    approval_summary = "{question}"

    def get_input_schema(self) -> type[ToolInput]:
        return AskUserInput

    async def execute(self, question: str, response_type: ResponseType = "text", options: list[str] | None = None) -> ToolOutput:
        # The HITL middleware answers this call with the user's reply, so this body is only a fallback.
        return ToolOutput(result="No reply was received from the user.")
