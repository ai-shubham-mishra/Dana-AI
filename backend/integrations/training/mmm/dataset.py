"""Compiles the MMM training dataset from org-scoped connector tables at run time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg_pool import AsyncConnectionPool

from integrations.connectors import catalog
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.mmm.recipe import DATE_COLUMN

MIN_ROWS = 20
NUMERIC_TYPES = frozenset({"smallint", "integer", "bigint", "numeric", "real", "double precision"})
DATE_TYPES = frozenset(
    {"date", "timestamp without time zone", "timestamp with time zone", "text", "character varying"}
)


@dataclass(frozen=True)
class DatasetResult:
    columns: list[str]
    rows: list[dict[str, Any]]


async def validate_sources(pool: AsyncConnectionPool, schema: str, plan: MMMPlan) -> None:
    for source in plan.sources:
        columns = await catalog.get_connector_columns(pool, schema, source.table)
        if columns is None:
            raise PlanError(f"connector table '{source.table}' does not exist")
        types = {column["name"]: column["data_type"] for column in columns}
        if catalog.ORG_COLUMN not in types:
            raise PlanError(f"'{source.table}' is shared across orgs and has no org_id; refusing to train on it")
        if source.date_column not in types:
            raise PlanError(f"date column '{source.date_column}' not found in '{source.table}'")
        if types[source.date_column] not in DATE_TYPES:
            raise PlanError(f"date column '{source.date_column}' in '{source.table}' is not a date type")
        for output, column in source.metrics.items():
            if column not in types:
                raise PlanError(f"column '{column}' not found in '{source.table}'")
            if types[column] not in NUMERIC_TYPES:
                raise PlanError(f"column '{column}' in '{source.table}' is {types[column]}, not numeric")


async def build_dataset(pool: AsyncConnectionPool, schema: str, org_id: str, plan: MMMPlan) -> DatasetResult:
    await validate_sources(pool, schema, plan)
    outputs = plan.output_names()
    by_day: dict[Any, dict[str, float]] = {}
    for source in plan.sources:
        names = list(source.metrics)
        rows = await catalog.get_daily_metric_rows(
            pool,
            schema,
            source.table,
            org_id,
            source.date_column,
            [source.metrics[name] for name in names],
            plan.date_start,
            plan.date_end,
        )
        for row in rows:
            day_values = by_day.setdefault(row["date"], {})
            for name, value in zip(names, row["values"], strict=True):
                day_values[name] = float(value) if value is not None else 0.0

    rows = []
    for day in sorted(by_day):
        values = by_day[day]
        if plan.kpi not in values:
            continue
        record: dict[str, Any] = {DATE_COLUMN: day.isoformat()}
        record.update({name: values.get(name, 0.0) for name in outputs})
        rows.append(record)
    if len(rows) < MIN_ROWS:
        raise PlanError(f"only {len(rows)} usable rows in the window; at least {MIN_ROWS} are needed")
    return DatasetResult(columns=[DATE_COLUMN, *outputs], rows=rows)
