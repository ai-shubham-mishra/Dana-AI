from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class SaveMLAssetsInput(ToolInput):
    job_id: str = Field(description="Id of the finished training job whose outputs should be saved.")


class SaveMLAssetsTool(PlannedTool):
    name: str = "save_ml_assets"
    description: str = "Save a finished job's model, charts and reports as assets the user can download."
    planned_reason = "Asset storage is not connected yet, so the job's outputs cannot be saved."

    def get_input_schema(self) -> type[ToolInput]:
        return SaveMLAssetsInput
