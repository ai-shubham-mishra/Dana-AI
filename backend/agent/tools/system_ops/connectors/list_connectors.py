from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.connectors.catalog import list_connectors
from integrations.connectors.channels import derive_channels


class ListConnectorsInput(ToolInput):
    """No arguments. Lists the org's data connectors (one per table in the org's datasets schema)."""


class ListConnectorsTool(ConnectorTool):
    name: str = "list_connectors"
    description: str = (
        "List the data connectors available to the user's organization, with channel counts and row estimates. "
        "Ask the user which connector to use."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ListConnectorsInput

    async def execute(self, **kwargs) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        connectors = await list_connectors(self.pool, self.datasets_schema)
        if not connectors:
            return ToolOutput(result="No connectors were found in the datasets schema.")
        lines = [f"Connectors ({len(connectors)}):"]
        for connector in connectors:
            channels = derive_channels(column["name"] for column in connector["columns"])
            scope = "org-scoped" if connector["org_scoped"] else "shared, no org_id column"
            rows = connector["row_estimate"]
            size = f"about {rows} rows" if rows is not None else "row count not analyzed yet"
            count = f"{len(channels)} channel{'' if len(channels) == 1 else 's'}"
            lines.append(f"- {connector['name']}: {count}, {size}, {scope}")
        return ToolOutput(result="\n".join(lines))
