from typing import Any

from pydantic import Field, ValidationError

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.ml_ops.ml.plans.common import request_plan_approval
from integrations.model_registry.registry import InvalidModelName, ModelNameTaken, normalize_model_name
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.scope import current_scope

RUN_PLAN_TOOL = "run_plan"


class RunPlanInput(ToolInput):
    plan_id: str = Field(description="Id of the plan to run, from list_plans.")
    model_name: str = Field(
        description="Name for the new model this run creates. Ask the user for it first. Max 80 characters."
    )


class RunPlanTool(BaseTool):
    name: str = RUN_PLAN_TOOL
    description: str = (
        "Train a new model from a saved plan with its exact stored configuration and date window. A run always creates "
        "a new model, never a new version of an existing one. Ask the user which plan to use and what to name the new "
        "model before calling this. The user sees the stored configuration on an approval card and must approve it."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return RunPlanInput

    async def execute(self, plan_id: str, model_name: str) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.plans is None or scope.service.models is None:
            return ToolOutput(success=False, error="Plans are unavailable in this context, so no run was started.")
        plan = await scope.plans.get_visible(org_id=scope.org_id, user_id=scope.user_id, plan_id=plan_id)
        if plan is None:
            return ToolOutput(success=False, error=f"No plan with id {plan_id} is visible to this user. Call list_plans first.")
        try:
            name = normalize_model_name(model_name)
        except InvalidModelName as exc:
            return ToolOutput(success=False, error=f"{exc}. Ask the user for a valid model name.")
        registry = scope.service.models
        if await registry.name_taken(org_id=scope.org_id, user_id=scope.user_id, name=name):
            suggestions = await registry.suggest_names(org_id=scope.org_id, user_id=scope.user_id, base=name)
            return ToolOutput(
                success=False,
                error=(
                    f"A model named '{name}' already exists. Ask the user to pick one of these unique suggestions: "
                    f"{', '.join(suggestions) or 'none available'}. Then call run_plan again with the chosen name."
                ),
            )
        try:
            recipe = MMMPlan(**plan["spec"])
        except (ValidationError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The saved plan cannot be run: {exc}")

        decision = request_plan_approval(
            RUN_PLAN_TOOL,
            {"plan": plan["name"], "plan_id": plan_id, "model": name, "configuration": plan["spec"]},
            f"Train a new model '{name}' from plan '{plan['name']}' with its saved configuration and date window? "
            "This always creates a new model.",
        )
        if decision.get("type") == "reject":
            reason = str(decision.get("message") or "").strip()
            suffix = f" Reason given: {reason}" if reason else ""
            return ToolOutput(result=f"The user rejected running plan '{plan['name']}'; no run was started.{suffix}")
        if decision.get("type") != "approve":
            return ToolOutput(success=False, error="Only approve or reject is accepted for this action.")

        try:
            job_id = await scope.service.submit_mmm_plan(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                plan=recipe,
                model_id=None,
                model_name=name,
                source="train",
                actor_email=scope.actor_email,
            )
        except ModelNameTaken as exc:
            return ToolOutput(
                success=False,
                error=f"A model named '{exc.name}' was created meanwhile. Suggestions: {', '.join(exc.suggestions)}.",
            )
        except (ValidationError, PlanError, InvalidModelName) as exc:
            return ToolOutput(success=False, error=f"The plan could not be run: {exc}")
        return ToolOutput(
            result=(
                f"Plan '{plan['name']}' is queued as job {job_id} to train the new model '{name}'. "
                "Progress is shown on the Jobs tab."
            ),
            metadata={"job_id": job_id},
        )
