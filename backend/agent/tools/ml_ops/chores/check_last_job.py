from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CheckLastJobInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLastJobTool(PlannedTool):
    name: str = "check_last_job"
    description: str = "Look up the most recent training job for the user's organization."
    planned_reason = "Job history is not connected yet, so the last job cannot be checked."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLastJobInput
