from typing import Any

from pydantic import Field

from agent.tools.base import BaseTool, ToolOutput
from integrations.connectors.catalog import list_connectors
from integrations.connectors.channels import describe_connector, format_channels
from integrations.training.scope import current_scope

NOT_CONFIGURED = "The connector database is not configured, so connectors cannot be read."
NO_SCOPE = "Connectors are unavailable in this context, so no organization could be identified."


class ConnectorTool(BaseTool):
    """Reads connector metadata for the signed-in org. The pool and schema are bound at startup."""

    pool: Any = Field(default=None, exclude=True)
    datasets_schema: str = "datasets"

    def _blocked(self) -> ToolOutput | None:
        if self.pool is None:
            return ToolOutput(success=False, error=NOT_CONFIGURED)
        if current_scope() is None:
            return ToolOutput(success=False, error=NO_SCOPE)
        return None

    async def describe_channels(self, connector: str) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        described = await describe_connector(self.pool, self.datasets_schema, connector, current_scope().org_id)
        if described is None:
            names = [item["name"] for item in await list_connectors(self.pool, self.datasets_schema)]
            return ToolOutput(
                success=False,
                error=f"Connector '{connector}' does not exist. Available connectors: {', '.join(names) or 'none'}.",
            )
        return ToolOutput(result=format_channels(described), metadata=described)
