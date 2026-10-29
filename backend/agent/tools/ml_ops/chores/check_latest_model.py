from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.job_view import describe_model, kind_for_family
from integrations.training.scope import current_scope


class CheckLatestModelInput(ToolInput):
    model_family: str | None = Field(default=None, description="Optional model family to filter by, for example 'mmm'.")


class CheckLatestModelTool(BaseTool):
    name: str = "check_latest_model"
    description: str = "Look up the latest successfully trained model and its saved artifact for the signed-in user."

    def get_input_schema(self) -> type[ToolInput]:
        return CheckLatestModelInput

    async def execute(self, model_family: str | None = None) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Model lookup is unavailable in this context.")
        job = await scope.service.find_latest_job(
            org_id=scope.org_id,
            user_id=scope.user_id,
            kind=kind_for_family(model_family),
            statuses=("succeeded",),
        )
        if job is None:
            return ToolOutput(result=f"No trained {model_family or 'model'} found for this user yet.")
        return ToolOutput(result=describe_model(job))
