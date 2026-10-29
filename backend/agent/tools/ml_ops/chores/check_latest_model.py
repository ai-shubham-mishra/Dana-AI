from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CheckLatestModelInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLatestModelTool(PlannedTool):
    name: str = "check_latest_model"
    description: str = "Look up the latest trained model artifact for a model family."
    planned_reason = "Model registry is not connected yet, so the latest model cannot be checked."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLatestModelInput
