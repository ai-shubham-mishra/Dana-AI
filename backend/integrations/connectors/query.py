from dataclasses import dataclass
from typing import Any

from psycopg_pool import AsyncConnectionPool

DEFAULT_ROW_LIMIT = 200
MAX_CELL_CHARS = 120


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool


async def run_readonly_query(pool: AsyncConnectionPool, guarded_sql: str, row_limit: int = DEFAULT_ROW_LIMIT) -> QueryResult:
    wrapped = f"SELECT * FROM ({guarded_sql}) AS query_result LIMIT {row_limit + 1}"
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL transaction_read_only = on")
            async with conn.cursor() as cur:
                await cur.execute(wrapped)
                columns = [column.name for column in cur.description or []]
                rows = await cur.fetchall()
    return QueryResult(columns=columns, rows=rows[:row_limit], truncated=len(rows) > row_limit)


def _cell(value: Any) -> str:
    if value is None:
        return "NULL"
    text = " ".join(str(value).split()).replace("|", "\\|")
    return text if len(text) <= MAX_CELL_CHARS else text[: MAX_CELL_CHARS - 1] + "…"


def format_query_result(result: QueryResult) -> str:
    if not result.columns:
        return "The query returned no columns."
    header = "| " + " | ".join(result.columns) + " |"
    divider = "|" + "|".join("---" for _ in result.columns) + "|"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in result.rows]
    lines = [header, divider, *body]
    if not result.rows:
        lines.append("(no rows)")
    if result.truncated:
        lines.append(f"Showing the first {len(result.rows)} rows. The result has more; aggregate or narrow the query.")
    return "\n".join(lines)
