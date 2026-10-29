from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool


class ListChannelsInput(ToolInput):
    connector: str = Field(description="Connector (table) whose channel columns should be listed.")


class ListChannelsTool(ConnectorTool):
    name: str = "list_channels"
    description: str = "List the channel columns available for modeling in a connector's table."

    def get_input_schema(self) -> type[ToolInput]:
        return ListChannelsInput

    async def execute(self, connector: str) -> ToolOutput:
        return await self.describe_channels(connector)
