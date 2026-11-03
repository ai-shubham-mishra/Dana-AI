import re

from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.connectors import catalog

MAX_MATCHES = 50
MAX_PATTERN_LENGTH = 100
LISTED_WHEN_NO_MATCH = 60


class FindConnectorColumnsInput(ToolInput):
    connector: str = Field(description="Name of the connector (table) whose columns to search.")
    pattern: str = Field(
        description=(
            "Case-insensitive regular expression matched against column names, for example 'gads.*spend' or "
            "'demand.?gen'. Use plain words for fuzzy matching, for example 'country|market'."
        ),
    )


class FindConnectorColumnsTool(ConnectorTool):
    name: str = "find_connector_columns"
    description: str = (
        "Find the columns of one connector whose names match a case-insensitive regular expression. Use it to match "
        "the user's wording to the real column names, which can differ per org and may contain hyphens or different "
        "casing. Read-only."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return FindConnectorColumnsInput

    async def execute(self, connector: str, pattern: str) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        if not pattern.strip() or len(pattern) > MAX_PATTERN_LENGTH:
            return ToolOutput(success=False, error=f"pattern must be 1 to {MAX_PATTERN_LENGTH} characters.")
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            return ToolOutput(success=False, error=f"pattern is not a valid regular expression: {error}.")

        columns = await catalog.get_connector_columns(self.pool, self.datasets_schema, connector)
        if columns is None:
            names = [item["name"] for item in await catalog.list_connectors(self.pool, self.datasets_schema)]
            return ToolOutput(
                success=False,
                error=f"Connector '{connector}' does not exist. Available connectors: {', '.join(names) or 'none'}.",
            )
        org_scoped = any(item["name"] == catalog.ORG_COLUMN for item in columns)
        matches = [item for item in columns if regex.search(item["name"])]
        if not matches:
            if len(columns) <= LISTED_WHEN_NO_MATCH:
                available = ", ".join(item["name"] for item in columns)
                return ToolOutput(
                    result=f"No columns in '{connector}' match '{pattern}'. Its columns are: {available}.",
                    metadata={"matches": [], "org_scoped": org_scoped},
                )
            return ToolOutput(
                result=f"No columns in '{connector}' match '{pattern}'. Try a broader pattern.",
                metadata={"matches": [], "org_scoped": org_scoped},
            )

        shown = matches[:MAX_MATCHES]
        lines = [f"- '{item['name']}' ({item['data_type']})" for item in shown]
        header = f"{len(matches)} column(s) in '{connector}' match '{pattern}':"
        if len(matches) > MAX_MATCHES:
            header = f"{len(matches)} column(s) in '{connector}' match '{pattern}'. Showing the first {MAX_MATCHES}:"
        note = "" if org_scoped else f"\n'{connector}' is shared across orgs and has no org_id."
        return ToolOutput(
            result="\n".join([header, *lines]) + note,
            metadata={
                "matches": [{"name": item["name"], "data_type": item["data_type"]} for item in shown],
                "truncated": len(matches) > MAX_MATCHES,
                "org_scoped": org_scoped,
            },
        )
