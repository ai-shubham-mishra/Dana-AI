from typing import Any

from pydantic import ValidationError

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.ml_ops.ml.training.start_mmm_run import StartMmmRunInput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.training.mmm.dataset import build_dataset
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.scope import current_scope

SAMPLE_HEAD = 3
SAMPLE_TAIL = 2


class PreviewMmmDatasetInput(StartMmmRunInput):
    pass


def _format_row(row: dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        parts.append(f"{key}={value:.2f}" if isinstance(value, float) else f"{key}={value}")
    return ", ".join(parts)


class PreviewMmmDatasetTool(ConnectorTool):
    name: str = "preview_mmm_dataset"
    description: str = (
        "Build the MMM training dataset for a plan without training. Applies the preparation (text to number, blanks "
        "filled with 0, lags, rolling means, calendar and holiday features) and returns row counts, the transform log "
        "and sample rows. Saves nothing. Use it to check the data before start_mmm_run. Read-only."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return PreviewMmmDatasetInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        org_id = current_scope().org_id
        try:
            plan = MMMPlan(**kwargs)
            dataset = await build_dataset(self.pool, self.datasets_schema, org_id, plan)
        except (ValidationError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The dataset cannot be built: {exc}. Fix the plan and preview again.")

        rows = dataset.rows
        log = dataset.log
        head = rows[:SAMPLE_HEAD]
        tail = rows[-SAMPLE_TAIL:] if len(rows) > SAMPLE_HEAD else []
        lines = [
            f"Dataset preview for KPI '{plan.kpi}': {log['rows_kept']} rows from {rows[0]['date']} to {rows[-1]['date']}.",
            f"Columns: {', '.join(dataset.columns)}.",
            f"Days dropped because the KPI had no row: {log['days_dropped_without_kpi']}.",
            "Blanks filled with 0 per output: "
            + (", ".join(f"{name} {count}" for name, count in log["blanks_filled"].items()) or "none")
            + ".",
            f"History read before the window: {log['history_days']} days.",
            *(
                ["Combined channels: " + "; ".join(f"{group} = {' + '.join(members)}" for group, members in log["combined"].items()) + "."]
                if log["combined"]
                else []
            ),
            "First rows:",
            *[f"- {_format_row(row)}" for row in head],
        ]
        if tail:
            lines += ["Last rows:", *[f"- {_format_row(row)}" for row in tail]]
        lines.append("Nothing was saved. Call start_mmm_run with the same plan to train.")
        return ToolOutput(result="\n".join(lines), metadata={"log": log, "columns": dataset.columns})
