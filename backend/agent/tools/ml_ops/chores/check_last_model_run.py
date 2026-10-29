from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CheckLastModelRunInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLastModelRunTool(PlannedTool):
    name: str = "check_last_model_run"
    description: str = "Look up the most recent model run, including its status and metrics."
    planned_reason = "Model run history is not connected yet, so the last run cannot be checked."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLastModelRunInput
