from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.mmm.request import RequestError
from integrations.training.scope import current_scope

START_TRAINING_JOB_TOOL = "start_training_job"


class StartTrainingJobInput(ToolInput):
    model: str = Field(description="Model family to train. Only 'mmm' is available today.")
    kpi: str = Field(description="Target KPI or metric the model predicts. Must match the dataset target.")
    channels: list[str] = Field(description="Marketing channels to include, from the dataset channel list.")
    date_range: str = Field(description="Training window in the form 'YYYY-MM-DD to YYYY-MM-DD', as returned by resolve_date_range.")


class StartTrainingJobTool(BaseTool):
    name: str = START_TRAINING_JOB_TOOL
    description: str = "Start a model training job. A human must approve, edit, or reject the request before this runs."
    allowed_decisions = ["approve", "edit", "reject"]
    approval_summary = "Start a {model} training job for KPI {kpi} on channels {channels} over {date_range}?"

    def get_input_schema(self) -> type[ToolInput]:
        return StartTrainingJobInput

    async def execute(self, model: str, kpi: str, channels: list[str], date_range: str) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Training is unavailable in this context, so no job was started.")
        try:
            job_id = await scope.service.submit(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                model=model,
                kpi=kpi,
                channels=channels,
                date_range=date_range,
            )
        except RequestError as exc:
            return ToolOutput(
                success=False,
                error=f"The training request is invalid: {exc}. Ask the user to correct it and try again.",
            )
        return ToolOutput(
            result=f"Training job {job_id} is queued on the bundled sample MMM dataset. Progress is shown on the Jobs tab."
        )
