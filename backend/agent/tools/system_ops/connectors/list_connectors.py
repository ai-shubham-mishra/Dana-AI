from agent.tools.base import ToolInput, PlannedTool


class ListConnectorsInput(ToolInput):
    """No arguments. Lists the org's data connectors (one per table in the org's datasets schema)."""


class ListConnectorsTool(PlannedTool):
    name: str = "list_connectors"
    description: str = "List the data connectors available to the user's organization."
    planned_reason = "Connector discovery is not connected yet, so connectors cannot be listed."

    def get_input_schema(self) -> type[ToolInput]:
        return ListConnectorsInput
