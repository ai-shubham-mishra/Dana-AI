from typing import Any

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from integrations.training.scope import current_scope

LIST_MODEL_VERSIONS_TOOL = "list_model_versions"


class ListModelVersionsInput(ToolInput):
    model_id: str | None = Field(
        default=None,
        description="Id of the model to inspect. Leave empty to list the user's models with their latest version.",
    )


def _channels(params: dict[str, Any]) -> str:
    channels = params.get("channels") or []
    return ", ".join(channels) if channels else "none"


def _describe_version(version: dict[str, Any]) -> str:
    params = version.get("params") or {}
    period = f"{params.get('date_start', '?')} to {params.get('date_end', '?')}"
    controls = ", ".join(params.get("controls") or []) or "none"
    return "\n".join(
        [
            f"- Version {version.get('version')} ({version.get('source', 'train')}, "
            f"created {version.get('created_at')} by {version.get('created_by_email') or 'unknown'}, "
            f"job {version.get('job_id')})",
            f"  KPI: {params.get('kpi', '?')}",
            f"  Channels: {_channels(params)}",
            f"  Controls: {controls}",
            f"  Period: {period}",
        ]
    )


class ListModelVersionsTool(BaseTool):
    name: str = LIST_MODEL_VERSIONS_TOOL
    description: str = (
        "List the user's saved models, or the versions of one model with the configuration each version was trained "
        "with (KPI, channels, controls, period). Use it to find the model and version the user means before "
        "retrain_model_version, which shows the saved configuration on its approval card."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ListModelVersionsInput

    async def execute(self, model_id: str | None = None) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.service.models is None:
            return ToolOutput(success=False, error="Model versions are unavailable in this context.")
        registry = scope.service.models
        if not model_id:
            models = await registry.list_models(org_id=scope.org_id, user_id=scope.user_id)
            if not models:
                return ToolOutput(result="The user has no saved models yet. Train one first.")
            lines = [
                f"- {m['id']}: {m.get('name')} (latest version {m.get('latest_version')}, "
                f"{m.get('version_count')} version(s))"
                for m in models
            ]
            return ToolOutput(result="\n".join(lines))
        versions = await registry.list_versions(org_id=scope.org_id, user_id=scope.user_id, model_id=model_id)
        if not versions:
            return ToolOutput(success=False, error=f"No model with id {model_id} was found for this user.")
        return ToolOutput(result=f"Model {model_id}:\n" + "\n".join(_describe_version(v) for v in versions))
