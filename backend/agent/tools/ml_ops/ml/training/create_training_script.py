from typing import Any

from pydantic import ValidationError

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.ml_ops.ml.training.start_mmm_run import StartMmmRunInput
from integrations.model_registry.registry import ModelNameTaken
from integrations.training.drafts import DraftError
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.scope import current_scope

CREATE_TRAINING_SCRIPT_TOOL = "create_training_script"


class CreateTrainingScriptInput(StartMmmRunInput):
    pass


class CreateTrainingScriptTool(BaseTool):
    name: str = CREATE_TRAINING_SCRIPT_TOOL
    description: str = (
        "Create a draft MMM training script for the org's connector data, starting from the MMM sample pipeline and "
        "adapted to the chosen KPI, channels, controls, window and preparation. Nothing runs yet. The result includes "
        "the full script and its sha256. Show the script to the user and let them review it. They can ask for changes, "
        "which you make with edit_training_script. Then call run_training_script with the run_id and sha256 the user "
        "reviewed. Use the same input as start_mmm_run. Ask for the training window and a new model name first."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return CreateTrainingScriptInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Training is unavailable in this context, so no draft was created.")
        model_id = kwargs.pop("model_id", None) or None
        model_name = kwargs.pop("model_name", None)
        if model_id is None and not model_name:
            return ToolOutput(
                success=False,
                error="A brand-new model needs a model_name. Ask the user for one, or pass model_id to retrain an existing model.",
            )
        try:
            plan = MMMPlan(**kwargs)
            draft = await scope.service.prepare_mmm_draft(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                plan=plan,
                model_id=model_id,
                model_name=None if model_id else model_name,
                source="retrain" if model_id else "train",
                actor_email=scope.actor_email,
            )
        except LookupError as exc:
            return ToolOutput(success=False, error=f"{exc}. Call list_models to find the correct model_id.")
        except ModelNameTaken as exc:
            suggestions = ", ".join(exc.suggestions) or "none available"
            return ToolOutput(
                success=False,
                error=(
                    f"A model named '{exc.name}' already exists. Ask the user to pick a different name, "
                    f"offering these unique suggestions: {suggestions}. Then call create_training_script again with the chosen name."
                ),
            )
        except (ValidationError, PlanError, DraftError) as exc:
            return ToolOutput(
                success=False,
                error=f"The MMM plan is invalid: {exc}. Fix the plan and call create_training_script again.",
            )
        return ToolOutput(
            result={
                "run_id": draft.run_id,
                "script_sha256": draft.script_sha256,
                "script": draft.script,
                "next": "Show the script to the user. Use edit_training_script for changes, then run_training_script with this run_id and the reviewed sha256.",
            }
        )
