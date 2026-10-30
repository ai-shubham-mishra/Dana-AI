from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.job_view import describe_job, describe_metrics, kind_for_family
from integrations.training.scope import current_scope


class CheckLastModelRunInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLastModelRunTool(BaseTool):
    name: str = "check_last_model_run"
    description: str = "Look up the most recent finished model run (succeeded or failed) with its status and metrics for the signed-in user."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLastModelRunInput

    async def execute(self, model_family: str | None = None) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Model run history is unavailable in this context.")
        job = await scope.service.find_latest_job(
            org_id=scope.org_id,
            user_id=scope.user_id,
            kind=kind_for_family(model_family),
            statuses=("succeeded", "failed"),
        )
        if job is None:
            return ToolOutput(result=f"No finished {model_family or 'model'} runs found for this user yet.")
        return ToolOutput(result="\n".join(part for part in (describe_job(job), describe_metrics(job)) if part))
