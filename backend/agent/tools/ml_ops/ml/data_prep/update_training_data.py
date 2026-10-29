from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class UpdateTrainingDataInput(ToolInput):
    dataset_id: str = Field(description="Id of the prepared training dataset to update.")
    changes: str = Field(description="Plain-language description of the change, for example 'drop the 2020 rows'.")


class UpdateTrainingDataTool(PlannedTool):
    name: str = "update_training_data"
    description: str = "Apply a change to a prepared training dataset after the user asks for an adjustment."
    planned_reason = "Dataset updates are not connected yet, so the training data was not changed."

    def get_input_schema(self) -> type[ToolInput]:
        return UpdateTrainingDataInput
