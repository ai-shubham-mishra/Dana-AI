from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput


class InitiateMLTrainingInput(ToolInput):
    model: str = Field(description="Model family to train, for example 'mmm'.")
    kpi: str = Field(description="Target KPI or metric the model predicts.")
    channels: list[str] = Field(description="Marketing channels to include in the model.")
    date_range: str = Field(description="Training window, for example '2024-01-01 to 2024-12-31'.")


class InitiateMLTrainingTool(BaseTool):
    name: str = "initiate_ml_training"
    description: str = (
        "Start a model training job. A human must approve, edit, or reject the request before this runs."
    )
    allowed_decisions = ["approve", "edit", "reject"]

    def get_input_schema(self) -> type[ToolInput]:
        return InitiateMLTrainingInput

    async def execute(self, model: str, kpi: str, channels: list[str], date_range: str) -> ToolOutput:
        # Training execution is not connected yet. The approval gate is the part under test here.
        return ToolOutput(
            result=(
                "Training execution is not connected yet, so no job was started. "
                f"Requested: model={model}, kpi={kpi}, channels={', '.join(channels)}, date_range={date_range}."
            )
        )
