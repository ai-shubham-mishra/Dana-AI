from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class ListChannelsWithinConnectorInput(ToolInput):
    connector: str = Field(description="Name of the connector (table) to read channels from.")


class ListChannelsWithinConnectorTool(PlannedTool):
    name: str = "list_channels_within_connector"
    description: str = (
        "List the marketing channels inside one connector. The user selects the connector first, "
        "so a human must approve or edit the connector choice before this runs."
    )
    allowed_decisions = ["approve", "edit", "reject"]
    planned_reason = "Connector channel discovery is not connected yet, so channels cannot be listed."

    def get_input_schema(self) -> type[ToolInput]:
        return ListChannelsWithinConnectorInput
