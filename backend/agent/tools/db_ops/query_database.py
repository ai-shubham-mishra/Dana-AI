import psycopg
from pydantic import Field

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.connectors.catalog import list_connectors
from integrations.connectors.query import format_query_result, run_readonly_query
from integrations.connectors.sql_guard import SqlRejected, guard_query
from integrations.training.scope import current_scope


class QueryDatabaseInput(ToolInput):
    """A single read-only SELECT over the connector tables."""

    query: str = Field(
        description=(
            "One PostgreSQL SELECT statement. Use the connector table names from list_connectors. "
            "Org-scoped tables are filtered to the signed-in organization automatically."
        )
    )


class QueryDatabaseTool(ConnectorTool):
    name: str = "query_database"
    description: str = (
        "Run one read-only PostgreSQL SELECT over the client's connector tables, for example to find the latest "
        "date, count rows, or aggregate a column. Results are limited to the signed-in organization and to 200 rows. "
        "Writes and other schemas are refused."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return QueryDatabaseInput

    async def execute(self, **kwargs) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        tables = {c["name"]: c["org_scoped"] for c in await list_connectors(self.pool, self.datasets_schema)}
        try:
            guarded = guard_query(
                kwargs["query"],
                schema=self.datasets_schema,
                org_id=current_scope().org_id,
                tables=tables,
            )
        except SqlRejected as exc:
            return ToolOutput(success=False, error=str(exc))
        try:
            result = await run_readonly_query(self.pool, guarded.sql)
        except psycopg.errors.QueryCanceled:
            return ToolOutput(
                success=False,
                error="The query ran longer than the 15 second limit and was stopped. Narrow it or aggregate in SQL.",
            )
        except psycopg.Error as exc:
            detail = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            return ToolOutput(success=False, error=f"The database rejected the query: {detail}")
        return ToolOutput(
            result=format_query_result(result),
            metadata={
                "row_count": len(result.rows),
                "truncated": result.truncated,
                "columns": result.columns,
                "tables": list(guarded.tables),
            },
        )
