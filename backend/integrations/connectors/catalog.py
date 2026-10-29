import math
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

_CONNECTORS_SQL = """
SELECT t.table_name, c.reltuples::bigint AS row_estimate
FROM information_schema.tables t
JOIN pg_namespace n ON n.nspname = t.table_schema
JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = t.table_name
WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name
"""

_SCHEMA_COLUMNS_SQL = """
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = %s
ORDER BY table_name, ordinal_position
"""

_TABLE_COLUMNS_SQL = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = %s AND table_name = %s
ORDER BY ordinal_position
"""

ORG_COLUMN = "org_id"


def _estimate(value: int | None) -> int | None:
    # reltuples is -1 until the table has been analyzed.
    return value if value is not None and value >= 0 else None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, bytes | memoryview):
        return f"<{len(bytes(value))} bytes>"
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


async def list_connectors(pool: AsyncConnectionPool, schema: str) -> list[dict[str, Any]]:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(_CONNECTORS_SQL, (schema,))
        tables = await cur.fetchall()
        await cur.execute(_SCHEMA_COLUMNS_SQL, (schema,))
        columns = await cur.fetchall()

    by_table: dict[str, list[dict[str, str]]] = {}
    for column in columns:
        by_table.setdefault(column["table_name"], []).append(
            {"name": column["column_name"], "data_type": column["data_type"]}
        )
    return [
        {
            "name": table["table_name"],
            "row_estimate": _estimate(table["row_estimate"]),
            "org_scoped": ORG_COLUMN in {column["name"] for column in by_table.get(table["table_name"], [])},
            "columns": by_table.get(table["table_name"], []),
        }
        for table in tables
    ]


async def get_connector_page(
    pool: AsyncConnectionPool,
    schema: str,
    table: str,
    org_id: str,
    page: int,
    page_size: int,
) -> dict[str, Any] | None:
    async with pool.connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(_TABLE_COLUMNS_SQL, (schema, table))
        columns = await cur.fetchall()
        if not columns:
            return None

        relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
        names = [column["column_name"] for column in columns]
        org_scoped = ORG_COLUMN in names
        scope = sql.SQL(" WHERE {}::text = %s").format(sql.Identifier(ORG_COLUMN)) if org_scoped else sql.SQL("")
        scope_params: tuple[str, ...] = (org_id,) if org_scoped else ()

        await cur.execute(sql.SQL("SELECT count(*) AS total FROM {}{}").format(relation, scope), scope_params)
        total = (await cur.fetchone())["total"]

        await cur.execute(
            sql.SQL("SELECT * FROM {}{} ORDER BY ctid LIMIT %s OFFSET %s").format(relation, scope),
            (*scope_params, page_size, (page - 1) * page_size),
        )
        rows = await cur.fetchall()

    return {
        "name": table,
        "org_scoped": org_scoped,
        "columns": [{"name": column["column_name"], "data_type": column["data_type"]} for column in columns],
        "rows": [[_jsonable(row[name]) for name in names] for row in rows],
        "page": page,
        "page_size": page_size,
        "total_rows": total,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


async def get_connector_columns(pool: AsyncConnectionPool, schema: str, table: str) -> list[dict[str, str]] | None:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(_TABLE_COLUMNS_SQL, (schema, table))
        columns = await cur.fetchall()
    if not columns:
        return None
    return [{"name": column["column_name"], "data_type": column["data_type"]} for column in columns]


async def count_org_rows(pool: AsyncConnectionPool, schema: str, table: str, org_id: str) -> int:
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    query = sql.SQL("SELECT count(*) AS total FROM {} WHERE {}::text = %s").format(
        relation, sql.Identifier(ORG_COLUMN)
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (org_id,))
        row = await cur.fetchone()
    return int(row["total"])
