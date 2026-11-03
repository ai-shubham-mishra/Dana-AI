from typing import Any

from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.connectors import catalog
from integrations.training.scope import current_scope

MAX_COLUMNS = 20
NUMERIC_SHARE = 0.9
MOSTLY_TEXT_SHARE = 0.5


class ProfileConnectorColumnsInput(ToolInput):
    connector: str = Field(description="Name of the connector (table) to profile.")
    columns: list[str] = Field(
        min_length=1,
        max_length=MAX_COLUMNS,
        description="Exact column names to profile, as returned by find_connector_columns.",
    )


def _recommendation(data_type: str, profile: dict[str, Any]) -> str:
    filled = profile["rows"] - profile["blank"]
    if data_type in catalog.TEXT_TYPES:
        if filled == 0:
            return "empty: do not use as a metric"
        share = profile["readable_as_number"] / filled
        if share >= NUMERIC_SHARE:
            return "text holding numbers: declare in preparation.text_to_numeric; unreadable values become 0"
        if share < MOSTLY_TEXT_SHARE:
            return "mostly non-numeric: do not use as a metric"
        return "mixed: inspect the unreadable samples before declaring it in preparation.text_to_numeric"
    return "numeric: use directly as a metric"


def _format_profile(name: str, data_type: str, profile: dict[str, Any]) -> str:
    lines = [
        f"- '{name}' ({data_type}): {profile['rows']} rows, {profile['blank']} blank, "
        f"{profile['readable_as_number']} readable as number, {profile['unreadable']} unreadable"
    ]
    if profile["min"] is not None:
        lines.append(f"  min {profile['min']}, max {profile['max']}, sum {profile['sum']}")
    if profile["unreadable_samples"]:
        lines.append(f"  unreadable samples: {', '.join(repr(v) for v in profile['unreadable_samples'])}")
    lines.append(f"  recommendation: {profile['recommendation']}")
    return "\n".join(lines)


class ProfileConnectorColumnsTool(ConnectorTool):
    name: str = "profile_connector_columns"
    description: str = (
        "Profile columns of one connector for the signed-in org: row count, blanks, values readable as numbers, "
        "unreadable samples, min, max and sum. Use it before training to decide whether a text column holds numbers "
        "that should be declared in preparation.text_to_numeric. Read-only."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ProfileConnectorColumnsInput

    async def execute(self, connector: str, columns: list[str]) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        org_id = current_scope().org_id
        known = await catalog.get_connector_columns(self.pool, self.datasets_schema, connector)
        if known is None:
            names = [item["name"] for item in await catalog.list_connectors(self.pool, self.datasets_schema)]
            return ToolOutput(
                success=False,
                error=f"Connector '{connector}' does not exist. Available connectors: {', '.join(names) or 'none'}.",
            )
        types = {item["name"]: item["data_type"] for item in known}
        missing = [column for column in columns if column not in types]
        if missing:
            return ToolOutput(
                success=False,
                error=f"Columns not found in '{connector}': {', '.join(missing)}. Use find_connector_columns first.",
            )
        if catalog.ORG_COLUMN not in types:
            return ToolOutput(success=False, error=f"'{connector}' is shared across orgs and has no org_id; it cannot be profiled.")

        profile = await catalog.profile_columns(self.pool, self.datasets_schema, connector, org_id, columns)
        for column in columns:
            profile[column]["recommendation"] = _recommendation(types[column], profile[column])
        text = "\n".join(_format_profile(column, types[column], profile[column]) for column in columns)
        return ToolOutput(
            result=f"Profile of {len(columns)} column(s) in '{connector}':\n{text}",
            metadata={"connector": connector, "columns": profile},
        )
