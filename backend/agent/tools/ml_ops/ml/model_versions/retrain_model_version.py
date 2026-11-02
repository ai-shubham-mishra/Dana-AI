from typing import Any

from langgraph.types import interrupt
from pydantic import Field, ValidationError

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.scope import current_scope

RETRAIN_MODEL_VERSION_TOOL = "retrain_model_version"
RETRAIN_DECISIONS = ["approve", "reject"]


class RetrainModelVersionInput(ToolInput):
    model_id: str = Field(description="Id of the model to retrain, from list_model_versions.")
    version: int = Field(description="Version whose saved configuration should be reused.")


def _first_decision(resume: Any) -> dict:
    decisions = resume.get("decisions") if isinstance(resume, dict) else None
    first = decisions[0] if decisions else None
    return first if isinstance(first, dict) else {}


class RetrainModelVersionTool(BaseTool):
    # Approval is requested inside execute(), not by the HITL middleware, so the approval card can show the
    # saved configuration. The middleware only sees the tool arguments.
    name: str = RETRAIN_MODEL_VERSION_TOOL
    description: str = (
        "Retrain a saved model with the exact configuration of one of its versions, producing a new version. "
        "The user sees that configuration on an approval card and must approve or reject it before the run starts. "
        "If the user did not name the model or version, call list_model_versions and ask which one to use."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return RetrainModelVersionInput

    async def execute(self, model_id: str, version: int) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.service.models is None:
            return ToolOutput(success=False, error="Retraining is unavailable in this context, so no run was started.")
        registry = scope.service.models
        model = await registry.get_model(org_id=scope.org_id, user_id=scope.user_id, model_id=model_id)
        source = await registry.get_version(org_id=scope.org_id, user_id=scope.user_id, model_id=model_id, version=version)
        if model is None or source is None:
            return ToolOutput(
                success=False,
                error=f"model {model_id} has no version {version}. Call list_model_versions to see the available versions.",
            )
        try:
            MMMPlan.model_validate(source["params"])
        except (ValidationError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The saved configuration cannot be retrained: {exc}")

        name = model.get("name") or model_id
        decision = _first_decision(
            interrupt(
                {
                    "action_requests": [
                        {
                            "name": RETRAIN_MODEL_VERSION_TOOL,
                            "args": {"model": name, "from_version": version, "configuration": source["params"]},
                            "description": (
                                f"Retrain {name} using the saved configuration of version {version}? "
                                "A new version is created when the run finishes."
                            ),
                        }
                    ],
                    "review_configs": [{"action_name": RETRAIN_MODEL_VERSION_TOOL, "allowed_decisions": RETRAIN_DECISIONS}],
                }
            )
        )
        if decision.get("type") == "reject":
            reason = str(decision.get("message") or "").strip()
            suffix = f" Reason given: {reason}" if reason else ""
            return ToolOutput(result=f"The user rejected retraining {name} from version {version}; no run was started.{suffix}")
        if decision.get("type") != "approve":
            return ToolOutput(success=False, error="Only approve or reject is accepted for this action.")

        try:
            job_id = await scope.service.retrain_version(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                model_id=model_id,
                version=version,
            )
        except LookupError as exc:
            return ToolOutput(success=False, error=f"{exc}. Call list_model_versions to see the available versions.")
        except (ValidationError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The saved configuration cannot be retrained: {exc}")
        return ToolOutput(
            result=(
                f"Retraining model {model_id} from version {version} is queued as job {job_id}. "
                "Progress is shown on the Jobs tab and the new version appears under the model."
            ),
            metadata={"job_id": job_id},
        )
