from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class PrepareTrainingDataInput(ToolInput):
    connector: str = Field(description="Connector (table) to read training data from.")
    kpi: str = Field(description="Target KPI column.")
    channels: list[str] = Field(description="Channel columns to keep.")
    date_range: str = Field(description="Training window, for example '2024-01-01 to 2024-12-31'.")


class PrepareTrainingDataTool(PlannedTool):
    name: str = "prepare_training_data"
    description: str = "Read the selected connector's table and shape it into a training dataset for the chosen KPI and channels."
    planned_reason = "Data preparation is not connected yet, so no training dataset was built."

    def get_input_schema(self) -> type[ToolInput]:
        return PrepareTrainingDataInput
