from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.job_view import describe_job, kind_for_family
from integrations.training.scope import current_scope


class CheckLastJobInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLastJobTool(BaseTool):
    name: str = "check_last_job"
    description: str = "Look up the most recent training job of any status for the signed-in user."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLastJobInput

    async def execute(self, model_family: str | None = None) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Job history is unavailable in this context.")
        job = await scope.service.find_latest_job(
            org_id=scope.org_id, user_id=scope.user_id, kind=kind_for_family(model_family)
        )
        if job is None:
            return ToolOutput(result=f"No {model_family or 'training'} jobs found for this user yet.")
        return ToolOutput(result=describe_job(job))
