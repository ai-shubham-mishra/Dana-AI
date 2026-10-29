from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CreateMLTrainingJobInput(ToolInput):
    model: str = Field(description="Model family to train, for example 'mmm'.")
    kpi: str = Field(description="Target KPI or metric the model predicts.")
    channels: list[str] = Field(description="Marketing channels to include in the model.")
    date_range: str = Field(description="Training window, for example '2024-01-01 to 2024-12-31'.")
    connector: str = Field(description="Connector (table) that holds the training data.")


class CreateMLTrainingJobTool(PlannedTool):
    name: str = "create_ml_training_job"
    description: str = "Create a training job record from an approved training request."
    planned_reason = "Job creation is not connected yet, so no training job was created."

    def get_input_schema(self) -> type[ToolInput]:
        return CreateMLTrainingJobInput
