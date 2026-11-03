import json
from typing import Any

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.model_registry.registry import ModelNameTaken
from integrations.training.drafts import DRAFT_META_FILE, DraftError, sha256_text
from integrations.training.mmm.plan import PlanError
from integrations.training.mmm.run_folder import TRAIN_FILE
from integrations.training.scope import current_scope

RUN_TRAINING_SCRIPT_TOOL = "run_training_script"
APPROVAL_SCRIPT_CHARS = 20_000


class RunTrainingScriptInput(ToolInput):
    run_id: str = Field(description="run_id of the draft returned by create_training_script.")
    script_sha256: str = Field(
        description="sha256 of the script the user reviewed, from create_training_script or edit_training_script. Training is refused if the script has changed since."
    )


class RunTrainingScriptTool(BaseTool):
    name: str = RUN_TRAINING_SCRIPT_TOOL
    description: str = (
        "Ask a human to approve training with a reviewed draft script. Training starts only after approval, and the "
        "approval shows the exact script. Pass the run_id and the script_sha256 the user reviewed. The run is refused "
        "if the script changed after review. Only call this after the user has reviewed the script."
    )
    allowed_decisions = ["approve", "reject"]

    def get_input_schema(self) -> type[ToolInput]:
        return RunTrainingScriptInput

    def approval_text(self, args: dict[str, Any]) -> str:
        run_id = str(args.get("run_id") or "")
        approved_sha = str(args.get("script_sha256") or "")
        scope = current_scope()
        if scope is None:
            return f"Run training script {run_id}? The draft cannot be loaded in this context, so nothing will run."
        try:
            run_dir = scope.service.draft_path(scope.org_id, scope.user_id, scope.chat_id, run_id)
            meta = json.loads((run_dir / DRAFT_META_FILE).read_text(encoding="utf-8"))
            script = (run_dir / TRAIN_FILE).read_text(encoding="utf-8")
        except (DraftError, OSError, ValueError) as exc:
            return f"Run training script {run_id}? The draft cannot be loaded ({type(exc).__name__}), so nothing will run."
        current_sha = sha256_text(script)
        target = meta.get("model_name") or f"a new version of model {meta.get('model_id')}"
        lines = [
            f"Train {target} on KPI {meta.get('kpi')} from {meta.get('date_start')} to {meta.get('date_end')} "
            f"({meta.get('rows')} rows)?",
            f"Script sha256: {current_sha}",
        ]
        if current_sha != approved_sha:
            lines.append("Warning: this differs from the sha256 that was requested, so the run will be refused.")
        shown = script[:APPROVAL_SCRIPT_CHARS]
        if len(script) > APPROVAL_SCRIPT_CHARS:
            shown += f"\n... script truncated, {len(script) - APPROVAL_SCRIPT_CHARS} more characters"
        lines.extend(["--- training script ---", shown])
        return "\n".join(lines)

    async def execute(self, **kwargs: Any) -> ToolOutput:
        scope = current_scope()
        if scope is None:
            return ToolOutput(success=False, error="Training is unavailable in this context, so nothing was started.")
        try:
            job_id = await scope.service.submit_mmm_draft(
                org_id=scope.org_id,
                user_id=scope.user_id,
                chat_id=scope.chat_id,
                run_id=kwargs["run_id"],
                script_sha256=kwargs["script_sha256"],
                actor_email=scope.actor_email,
            )
        except LookupError as exc:
            return ToolOutput(success=False, error=f"{exc}. Call create_training_script again to make a new draft.")
        except ModelNameTaken as exc:
            suggestions = ", ".join(exc.suggestions) or "none available"
            return ToolOutput(
                success=False,
                error=(
                    f"A model named '{exc.name}' already exists. Ask the user to pick a different name, "
                    f"offering these unique suggestions: {suggestions}. Then create a new draft with the chosen name."
                ),
            )
        except (DraftError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The draft cannot be run: {exc}")
        return ToolOutput(
            result=(
                f"MMM training run {job_id} is queued from the approved script. "
                "Progress is shown on the Jobs tab."
            )
        )
