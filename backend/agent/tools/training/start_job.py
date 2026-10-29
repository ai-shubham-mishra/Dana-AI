from langchain_core.tools import tool
from pydantic import BaseModel, Field

START_TRAINING_JOB_TOOL = "start_training_job"


class StartTrainingJobInput(BaseModel):
    model: str = Field(description="Model family to train, for example 'mmm'.")
    kpi: str = Field(description="Target KPI or metric the model predicts.")
    channels: list[str] = Field(description="Marketing channels to include in the model.")
    date_range: str = Field(description="Training window, for example '2024-01-01 to 2024-12-31'.")


@tool(START_TRAINING_JOB_TOOL, args_schema=StartTrainingJobInput)
def start_training_job(model: str, kpi: str, channels: list[str], date_range: str) -> str:
    """Start a model training job. A human must approve, edit, or reject the request before this runs."""
    # Placeholder until training execution is connected. The approval gate is the part under test here.
    return (
        "Training execution is not connected yet, so no job was started. "
        f"Requested: model={model}, kpi={kpi}, channels={', '.join(channels)}, date_range={date_range}."
    )
