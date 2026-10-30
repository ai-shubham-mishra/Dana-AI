from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.job_view import describe_job, describe_metrics
from integrations.training.scope import current_scope


class CheckJobStatusInput(ToolInput):
    job_id: str = Field(description="Id of the training job to check.")


class CheckJobStatusTool(BaseTool):
    name: str = "check_job_status"
    description: str = "Check the status, progress and outcome of a training job by id for the signed-in user."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckJobStatusInput

    async def execute(self, job_id: str) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Job status is unavailable in this context.")
        job = await scope.service.get_job(org_id=scope.org_id, user_id=scope.user_id, job_id=job_id)
        if job is None:
            return ToolOutput(success=False, error=f"No training job with id {job_id} was found for this user.")
        return ToolOutput(result="\n".join(part for part in (describe_job(job), describe_metrics(job)) if part))
