from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CreateTrainingScriptInput(ToolInput):
    model: str = Field(description="Model family to train, for example 'mmm'.")
    kpi: str = Field(description="Target KPI column in the connector's table.")
    channels: list[str] = Field(description="Channel columns to model.")
    date_range: str = Field(description="Training window, for example '2024-01-01 to 2024-12-31'.")


class CreateTrainingScriptTool(PlannedTool):
    name: str = "create_training_script"
    description: str = (
        "Generate a training script for this client's data, starting from the MMM sample pipeline "
        "and adapted to the selected columns and channels."
    )
    planned_reason = "Script generation is not connected yet, so no training script was created."

    def get_input_schema(self) -> type[ToolInput]:
        return CreateTrainingScriptInput
