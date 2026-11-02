from pydantic import Field, ValidationError

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.mmm.plan import PlanError
from integrations.training.scope import current_scope

RETRAIN_MODEL_VERSION_TOOL = "retrain_model_version"


class RetrainModelVersionInput(ToolInput):
    model_id: str = Field(description="Id of the model to retrain, from list_model_versions.")
    version: int = Field(description="Version whose saved configuration should be reused.")


class RetrainModelVersionTool(BaseTool):
    name: str = RETRAIN_MODEL_VERSION_TOOL
    description: str = (
        "Retrain a saved model with the exact configuration of one of its versions, producing a new version. "
        "Call list_model_versions first and show the configuration to the user. A human must approve, edit, or "
        "reject before this runs."
    )
    allowed_decisions = ["approve", "edit", "reject"]
    approval_summary = "Retrain model {model_id} using the saved configuration of version {version}?"

    def get_input_schema(self) -> type[ToolInput]:
        return RetrainModelVersionInput

    async def execute(self, model_id: str, version: int) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.service.models is None:
            return ToolOutput(success=False, error="Retraining is unavailable in this context, so no run was started.")
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
