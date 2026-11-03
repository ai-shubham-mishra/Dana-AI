from typing import Any

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.drafts import DraftError
from integrations.training.scope import current_scope


class EditTrainingScriptInput(ToolInput):
    run_id: str = Field(description="run_id of the draft from create_training_script.")
    old_text: str = Field(description="Exact text to replace. It must appear exactly once in the script.")
    new_text: str = Field(description="Replacement text. Use an empty string to delete old_text.")


class EditTrainingScriptTool(BaseTool):
    name: str = "edit_training_script"
    description: str = (
        "Change a draft training script by replacing one exact passage. old_text must match exactly once. "
        "Returns the new script_sha256. Give that sha256 to run_training_script after the user approves the edit."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return EditTrainingScriptInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Training is unavailable in this context, so the draft was not changed.")
        try:
            digest = await scope.service.edit_mmm_draft(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                run_id=kwargs["run_id"],
                old_text=kwargs["old_text"],
                new_text=kwargs["new_text"],
            )
        except LookupError as exc:
            return ToolOutput(success=False, error=f"{exc}. Call create_training_script again to make a new draft.")
        except DraftError as exc:
            return ToolOutput(success=False, error=f"The script was not changed: {exc}")
        return ToolOutput(
            result={
                "script_sha256": digest,
                "next": "Show the updated script to the user. Then call run_training_script with this sha256 once they approve it.",
            }
        )
