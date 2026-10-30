from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool


class ListChannelsWithinConnectorInput(ToolInput):
    connector: str = Field(description="Name of the connector (table) to read channels from.")


class ListChannelsWithinConnectorTool(ConnectorTool):
    name: str = "list_channels_within_connector"
    description: str = (
        "List the marketing channels inside one connector. The user selects the connector first, "
        "so a human must approve or edit the connector choice before this runs."
    )
    allowed_decisions = ["approve", "edit", "reject"]
    approval_summary = "Read the marketing channels inside connector {connector}?"

    def get_input_schema(self) -> type[ToolInput]:
        return ListChannelsWithinConnectorInput

    async def execute(self, connector: str) -> ToolOutput:
        return await self.describe_channels(connector)
