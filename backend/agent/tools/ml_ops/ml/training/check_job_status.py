from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CheckJobStatusInput(ToolInput):
    job_id: str = Field(description="Id of the training job to check.")


class CheckJobStatusTool(PlannedTool):
    name: str = "check_job_status"
    description: str = "Check the status and progress of a training job."
    planned_reason = "Job tracking is not connected yet, so the job status cannot be checked."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckJobStatusInput
