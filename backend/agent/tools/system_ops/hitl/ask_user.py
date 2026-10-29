from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput


class AskUserInput(ToolInput):
    question: str = Field(description="One specific question for the user, for example 'Which KPI should the model predict?'.")
    options: list[str] | None = Field(
        default=None,
        description="Optional 2-6 short choices when the answer comes from a known set. The user may still type another answer.",
    )


class AskUserTool(BaseTool):
    name: str = "ask_user"
    description: str = (
        "Ask the user a clarifying question when information needed to proceed is missing. "
        "The user's reply is returned as this tool's result."
    )
    allowed_decisions = ["respond"]

    def get_input_schema(self) -> type[ToolInput]:
        return AskUserInput

    async def execute(self, question: str, options: list[str] | None = None) -> ToolOutput:
        # The HITL middleware answers this call with the user's reply, so this body is only a fallback.
        return ToolOutput(result="No reply was received from the user.")
