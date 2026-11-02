from datetime import date
from typing import Any

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.ml_ops.ml.plans.common import request_plan_approval
from integrations.plans.store import InvalidPlan, PlanNameTaken, normalize_plan_name, validate_spec, validate_visibility
from integrations.training.mmm.plan import PreparationSpec, SourceSpec
from integrations.training.scope import current_scope

SAVE_PLAN_TOOL = "save_plan"


class SavePlanInput(ToolInput):
    name: str = Field(description="Name for the plan, unique for the user. Max 80 characters.")
    description: str = Field(default="", description="What this plan is for, in one sentence.")
    visibility: str = Field(
        default="private",
        description="private keeps the plan to this user. org shares it with the organization, showing who created it.",
    )
    kpi: str = Field(description="Output name of the KPI to predict. Must be one of the mapped metric outputs.")
    channels: list[str] = Field(description="Output names of the marketing channels to model.")
    controls: list[str] = Field(default_factory=list, description="Output names of control variables.")
    controls_reason: str = Field(default="", description="Required only when controls is empty.")
    sources: list[SourceSpec] = Field(description="Connector tables to read, with table, date_column and metrics.")
    date_start: date = Field(description="First date of the training window, YYYY-MM-DD.")
    date_end: date = Field(description="Last date of the training window, YYYY-MM-DD.")
    preparation: PreparationSpec = Field(default_factory=PreparationSpec, description="Data preparation after profiling.")
    overrides: dict[str, Any] = Field(default_factory=dict, description="Optional whitelisted config overrides.")


class SavePlanTool(BaseTool):
    name: str = SAVE_PLAN_TOOL
    description: str = (
        "Save the training recipe from this conversation as a reusable plan. Call it only when the user explicitly asks "
        "to save a plan. The user approves the saved configuration on an approval card before anything is stored."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return SavePlanInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.plans is None:
            return ToolOutput(success=False, error="Plans are unavailable in this context, so nothing was saved.")
        name = ""
        try:
            name = normalize_plan_name(kwargs.pop("name", ""))
            description = (kwargs.pop("description", "") or "").strip()
            visibility = validate_visibility(kwargs.pop("visibility", "private") or "private")
            spec = validate_spec(kwargs)
            await scope.plans.ensure_name_free(org_id=scope.org_id, user_id=scope.user_id, name=name)
        except PlanNameTaken as exc:
            return ToolOutput(
                success=False,
                error=f"A plan named '{exc.name}' already exists. Ask the user for a different name, then call save_plan again.",
            )
        except InvalidPlan as exc:
            return ToolOutput(success=False, error=f"{exc}. Fix the plan and call save_plan again.")

        reach = "shared with the organization" if visibility == "org" else "private to this user"
        decision = request_plan_approval(
            SAVE_PLAN_TOOL,
            {"name": name, "description": description, "visibility": visibility, "configuration": spec},
            f"Save plan '{name}' ({reach})? Running a saved plan always creates a new model.",
        )
        if decision.get("type") == "reject":
            reason = str(decision.get("message") or "").strip()
            suffix = f" Reason given: {reason}" if reason else ""
            return ToolOutput(result=f"The user rejected saving the plan '{name}'; nothing was saved.{suffix}")
        if decision.get("type") != "approve":
            return ToolOutput(success=False, error="Only approve or reject is accepted for this action.")

        try:
            doc = await scope.plans.create(
                org_id=scope.org_id,
                user_id=scope.user_id,
                owner_email=scope.actor_email,
                name=name,
                description=description,
                visibility=visibility,
                spec=spec,
            )
        except (PlanNameTaken, InvalidPlan) as exc:
            return ToolOutput(success=False, error=f"The plan was not saved: {exc}")
        return ToolOutput(
            result=f"Saved plan '{doc['name']}' (id {doc['id']}, {visibility}). It appears on the Plans page and with /plans.",
            metadata={"plan_id": doc["id"]},
        )
