from langchain_core.tools import tool
from pydantic import BaseModel, Field

ASK_USER_TOOL = "ask_user"


class AskUserInput(BaseModel):
    question: str = Field(description="One specific question for the user, for example 'Which KPI should the model predict?'.")
    options: list[str] | None = Field(
        default=None,
        description="Optional 2-6 short choices when the answer comes from a known set. The user may still type another answer.",
    )


@tool(ASK_USER_TOOL, args_schema=AskUserInput)
def ask_user(question: str, options: list[str] | None = None) -> str:
    """Ask the user a clarifying question when information needed to proceed is missing. The user's reply is returned as this tool's result."""
    # HumanInTheLoopMiddleware answers this call with the user's reply, so this body is only a fallback.
    return "No reply was received from the user."
