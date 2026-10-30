from datetime import date
from typing import Any

from pydantic import Field, ValidationError

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.mmm.plan import MMMPlan, PlanError, SourceSpec
from integrations.training.scope import current_scope

START_MMM_RUN_TOOL = "start_mmm_run"


class StartMmmRunInput(ToolInput):
    kpi: str = Field(description="Output name of the KPI to predict. Must be one of the mapped metric outputs.")
    channels: list[str] = Field(description="Output names of the marketing channels to model, all from the mapped metrics.")
    controls: list[str] = Field(default_factory=list, description="Output names of control variables, such as price or promo flags.")
    sources: list[SourceSpec] = Field(
        description="Connector tables to read. Each has table, date_column and metrics, where metrics maps an output name to a source column."
    )
    date_start: date = Field(description="First date of the training window, YYYY-MM-DD.")
    date_end: date = Field(description="Last date of the training window, YYYY-MM-DD.")
    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional whitelisted config overrides: adstock_l_max, yearly_seasonality, time_varying_intercept, chains, tune, draws, holdout_periods.",
    )
    rationale: str = Field(default="", description="Short data-scientist reasoning for these choices, shown to the user on approval.")


class StartMmmRunTool(BaseTool):
    name: str = START_MMM_RUN_TOOL
    description: str = (
        "Start an MMM training run on the org's connector data. The dataset, config and training script are "
        "generated for this run. A human must approve, edit, or reject the plan before this runs."
    )
    allowed_decisions = ["approve", "edit", "reject"]

    def get_input_schema(self) -> type[ToolInput]:
        return StartMmmRunInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Training is unavailable in this context, so no run was started.")
        try:
            plan = MMMPlan(**kwargs)
            job_id = await scope.service.submit_mmm_plan(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                plan=plan,
            )
        except (ValidationError, PlanError) as exc:
            return ToolOutput(
                success=False,
                error=f"The MMM plan is invalid: {exc}. Fix the plan and call start_mmm_run again.",
            )
        return ToolOutput(
            result=(
                f"MMM training run {job_id} is queued. The dataset, config and training script are saved in its run folder. "
                "Progress is shown on the Jobs tab."
            )
        )
