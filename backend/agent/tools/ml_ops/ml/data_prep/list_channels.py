from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class ListChannelsInput(ToolInput):
    connector: str = Field(description="Connector (table) whose channel columns should be listed.")


class ListChannelsTool(PlannedTool):
    name: str = "list_channels"
    description: str = "List the channel columns available for modeling in a connector's table."
    planned_reason = "Channel listing is not connected yet, so the channels cannot be read from the connector."

    def get_input_schema(self) -> type[ToolInput]:
        return ListChannelsInput
