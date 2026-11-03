import math
import re
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


DATE_TYPES = frozenset({"date", "timestamp without time zone", "timestamp with time zone"})
TEXT_TYPES = frozenset({"text", "character varying", "character"})
DATE_NAME_HINT = re.compile(r"date|week|day|month|period", re.IGNORECASE)
ISO_DATE_PREFIX = r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
MAX_DATE_COLUMNS = 5


def is_date_column(column: dict[str, str]) -> bool:
    if column["data_type"] in DATE_TYPES:
        return True
    return column["data_type"] in TEXT_TYPES and bool(DATE_NAME_HINT.search(column["name"]))


def date_candidates(columns: list[dict[str, str]]) -> list[dict[str, str]]:
    return [column for column in columns if is_date_column(column)][:MAX_DATE_COLUMNS]


def _day_expression(column: dict[str, str]) -> sql.Composable:
    identifier = sql.Identifier(column["name"])
    if column["data_type"] == "date":
        return identifier
    if column["data_type"] in DATE_TYPES:
        return sql.SQL("CAST({} AS date)").format(identifier)
    return sql.SQL("CAST(substring({}::text from %s) AS date)").format(identifier)


async def get_date_ranges(
    pool: AsyncConnectionPool, schema: str, table: str, org_id: str | None, columns: list[dict[str, str]]
) -> dict[str, dict[str, Any]]:
    candidates = date_candidates(columns)
    if not candidates:
        return {}
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    days = []
    aggregates = []
    params: list[Any] = []
    for index, column in enumerate(candidates):
        days.append(sql.SQL("{} AS _d{}").format(_day_expression(column), sql.SQL(str(index))))
        if column["data_type"] not in DATE_TYPES:
            params.append(ISO_DATE_PREFIX)
        aggregates.append(sql.SQL("MIN(_d{i}) AS _min{i}, MAX(_d{i}) AS _max{i}, COUNT(_d{i}) AS _n{i}").format(i=index))
    scope = sql.SQL(" WHERE {}::text = %s").format(sql.Identifier(ORG_COLUMN)) if org_id is not None else sql.SQL("")
    if org_id is not None:
        params.append(org_id)
    query = sql.SQL("SELECT {aggregates} FROM (SELECT {days} FROM {relation}{scope}) AS _rows").format(
        aggregates=sql.SQL(", ").join(aggregates),
        days=sql.SQL(", ").join(days),
        relation=relation,
        scope=scope,
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, tuple(params))
        row = await cur.fetchone()
    ranges: dict[str, dict[str, Any]] = {}
    for index, column in enumerate(candidates):
        if not row[f"_n{index}"]:
            continue
        ranges[column["name"]] = {
            "data_type": column["data_type"],
            "earliest": row[f"_min{index}"].isoformat(),
            "latest": row[f"_max{index}"].isoformat(),
            "rows_with_date": int(row[f"_n{index}"]),
        }
    return ranges


async def count_org_rows(pool: AsyncConnectionPool, schema: str, table: str, org_id: str) -> int:
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    query = sql.SQL("SELECT count(*) AS total FROM {} WHERE {}::text = %s").format(
        relation, sql.Identifier(ORG_COLUMN)
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (org_id,))
        row = await cur.fetchone()
    return int(row["total"])


TEXT_CLEAN_PATTERN = "[[:space:],$€£]"
TEXT_NUMBER_PATTERN = r"^[-+]?([0-9]+[.]?[0-9]*|[.][0-9]+)$"


def _numeric_from_text(column: sql.Identifier) -> sql.Composable:
    """Text read as a number: spaces, commas and currency signs removed. Anything else is NULL."""
    cleaned = sql.SQL("regexp_replace({}::text, {}, '', 'g')").format(column, sql.Literal(TEXT_CLEAN_PATTERN))
    return sql.SQL("CASE WHEN {cleaned} ~ {pattern} THEN ({cleaned})::numeric END").format(
        cleaned=cleaned, pattern=sql.Literal(TEXT_NUMBER_PATTERN)
    )


async def get_daily_metric_rows(
    pool: AsyncConnectionPool,
    schema: str,
    table: str,
    org_id: str,
    date_column: str,
    metric_columns: list[str],
    start: date,
    end: date,
    filters: dict[str, str] | None = None,
    text_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    day = sql.SQL("CAST({} AS date)").format(sql.Identifier(date_column))
    text = set(text_columns or [])
    aggregates = []
    for index, column in enumerate(metric_columns):
        identifier = sql.Identifier(column)
        if column in text:
            expression = sql.SQL("SUM(COALESCE({}, 0))").format(_numeric_from_text(identifier))
        else:
            expression = sql.SQL("SUM({})").format(identifier)
        aggregates.append(sql.SQL("{} AS {}").format(expression, sql.Identifier(f"_m{index}")))
    conditions = [sql.SQL("{org}::text = %s").format(org=sql.Identifier(ORG_COLUMN))]
    params: list[Any] = [org_id]
    for column, value in (filters or {}).items():
        conditions.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
        params.append(value)
    conditions.append(sql.SQL("{day} BETWEEN %s AND %s").format(day=day))
    params.extend([start, end])
    query = sql.SQL(
        "SELECT {day} AS _day, {aggregates} FROM {relation} WHERE {conditions} GROUP BY 1 ORDER BY 1"
    ).format(
        day=day,
        aggregates=sql.SQL(", ").join(aggregates),
        relation=relation,
        conditions=sql.SQL(" AND ").join(conditions),
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, tuple(params))
        rows = await cur.fetchall()
    return [
        {
            "date": row["_day"],
            "values": [row[f"_m{index}"] for index in range(len(metric_columns))],
        }
        for row in rows
    ]


async def profile_columns(
    pool: AsyncConnectionPool,
    schema: str,
    table: str,
    org_id: str,
    columns: list[str],
) -> dict[str, dict[str, Any]]:
    """Per column: rows, blanks, values readable as numbers, unreadable values and their sum."""
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    aggregates = [sql.SQL("COUNT(*) AS _total")]
    for index, column in enumerate(columns):
        identifier = sql.Identifier(column)
        text_form = sql.SQL("{}::text").format(identifier)
        blank = sql.SQL("({} IS NULL OR btrim({}) = '')").format(identifier, text_form)
        parsed = _numeric_from_text(identifier)
        aggregates.extend(
            [
                sql.SQL("COUNT(*) FILTER (WHERE {}) AS _blank_{}").format(blank, index),
                sql.SQL("COUNT({}) AS _numeric_{}").format(parsed, index),
                sql.SQL("COUNT(*) FILTER (WHERE NOT {blank} AND {parsed} IS NULL) AS _unreadable_{i}").format(
                    blank=blank, parsed=parsed, i=index
                ),
                sql.SQL("MIN({}) AS _min_{}").format(parsed, index),
                sql.SQL("MAX({}) AS _max_{}").format(parsed, index),
                sql.SQL("SUM({}) AS _sum_{}").format(parsed, index),
                sql.SQL(
                    "(ARRAY_AGG(DISTINCT {text}) FILTER (WHERE NOT {blank} AND {parsed} IS NULL))[1:5] AS _samples_{i}"
                ).format(text=text_form, blank=blank, parsed=parsed, i=index),
            ]
        )
    query = sql.SQL("SELECT {aggregates} FROM {relation} WHERE {org}::text = %s").format(
        aggregates=sql.SQL(", ").join(aggregates),
        relation=relation,
        org=sql.Identifier(ORG_COLUMN),
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, (org_id,))
        row = await cur.fetchone()
    profile: dict[str, dict[str, Any]] = {}
    for index, column in enumerate(columns):
        profile[column] = {
            "rows": row["_total"],
            "blank": row[f"_blank_{index}"],
            "readable_as_number": row[f"_numeric_{index}"],
            "unreadable": row[f"_unreadable_{index}"],
            "min": _json_number(row[f"_min_{index}"]),
            "max": _json_number(row[f"_max_{index}"]),
            "sum": _json_number(row[f"_sum_{index}"]),
            "unreadable_samples": row[f"_samples_{index}"] or [],
        }
    return profile


def _json_number(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_column_values(
    pool: AsyncConnectionPool,
    schema: str,
    table: str,
    org_id: str,
    column: str,
    date_column: dict[str, str],
    limit: int,
) -> list[dict[str, Any]]:
    relation = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
    params: list[Any] = []
    if date_column["data_type"] not in DATE_TYPES:
        params.append(ISO_DATE_PREFIX)
    params.extend([org_id, limit])
    query = sql.SQL(
        "SELECT _value AS value, count(*) AS row_count, min(_day) AS first_date, max(_day) AS last_date "
        "FROM (SELECT {value} AS _value, {day} AS _day FROM {relation} "
        "WHERE {org}::text = %s AND {value} IS NOT NULL) AS _rows "
        "GROUP BY 1 ORDER BY row_count DESC, value LIMIT %s"
    ).format(
        value=sql.Identifier(column),
        day=_day_expression(date_column),
        relation=relation,
        org=sql.Identifier(ORG_COLUMN),
    )
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, tuple(params))
        rows = await cur.fetchall()
    return [dict(row) for row in rows]
