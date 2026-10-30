from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.connectors import catalog
from integrations.training.scope import current_scope

MAX_VALUES = 50


class ListConnectorColumnValuesInput(ToolInput):
    connector: str = Field(description="Name of the connector (table) to read from.")
    column: str = Field(description="Text column whose stored values you need, for example a country or market column.")
    date_column: str = Field(description="The connector's date column, used to show each value's date coverage.")


class ListConnectorColumnValuesTool(ConnectorTool):
    name: str = "list_connector_column_values"
    description: str = (
        "List the distinct values stored in a text column of one connector for the signed-in org, with row counts "
        "and date coverage. Use it to map the user's wording to stored values, for example 'Germany' to 'DE'. Read-only."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ListConnectorColumnValuesInput

    async def execute(self, connector: str, column: str, date_column: str) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        org_id = current_scope().org_id
        columns = await catalog.get_connector_columns(self.pool, self.datasets_schema, connector)
        if columns is None:
            names = [item["name"] for item in await catalog.list_connectors(self.pool, self.datasets_schema)]
            return ToolOutput(
                success=False,
                error=f"Connector '{connector}' does not exist. Available connectors: {', '.join(names) or 'none'}.",
            )
        types = {item["name"]: item["data_type"] for item in columns}
        if catalog.ORG_COLUMN not in types:
            return ToolOutput(success=False, error=f"'{connector}' is shared across orgs and has no org_id, so it cannot be read here.")
        if column not in types or types[column] not in catalog.TEXT_TYPES:
            return ToolOutput(success=False, error=f"'{column}' is not a text column in '{connector}'.")
        if date_column not in types or types[date_column] not in catalog.DATE_TYPES:
            return ToolOutput(success=False, error=f"'{date_column}' is not a date column in '{connector}'.")

        rows = await catalog.get_column_values(
            self.pool, self.datasets_schema, connector, org_id, column, date_column, MAX_VALUES + 1
        )
        truncated = len(rows) > MAX_VALUES
        rows = rows[:MAX_VALUES]
        values = [
            {
                "value": str(row["value"]),
                "row_count": int(row["row_count"]),
                "first_date": row["first_date"].isoformat() if row["first_date"] else None,
                "last_date": row["last_date"].isoformat() if row["last_date"] else None,
            }
            for row in rows
        ]
        if not values:
            return ToolOutput(result=f"No values are stored in '{column}' for this org in '{connector}'.", metadata={"values": []})
        lines = [
            f"- '{item['value']}': {item['row_count']} rows, {item['first_date']} to {item['last_date']}"
            for item in values
        ]
        scope_note = f"Top {len(values)} values (more exist)" if truncated else f"{len(values)} values"
        header = f"{scope_note} stored in '{connector}.{column}':"

        return ToolOutput(result="\n".join([header, *lines]), metadata={"values": values, "truncated": truncated})
