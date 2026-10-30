"""Compiles the MMM training dataset from org-scoped connector tables at run time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from psycopg_pool import AsyncConnectionPool

from integrations.connectors import catalog
from integrations.training.mmm.plan import MMMPlan, PlanError
from integrations.training.mmm.prep import build_rows
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
    log: dict[str, Any] = field(default_factory=dict)


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
        for column in source.filters:
            if column not in types:
                raise PlanError(f"filter column '{column}' not found in '{source.table}'")
            if types[column] not in catalog.TEXT_TYPES:
                raise PlanError(f"filter column '{column}' in '{source.table}' is {types[column]}, not text")
        for output, column in source.metrics.items():
            if column not in types:
                raise PlanError(f"column '{column}' not found in '{source.table}'")
            if types[column] in catalog.TEXT_TYPES:
                if output not in plan.preparation.text_to_numeric:
                    raise PlanError(
                        f"column '{column}' in '{source.table}' is text; profile it and declare "
                        f"'{output}' in preparation.text_to_numeric to read it as a number"
                    )
            elif types[column] not in NUMERIC_TYPES:
                raise PlanError(f"column '{column}' in '{source.table}' is {types[column]}, not numeric")


async def build_dataset(pool: AsyncConnectionPool, schema: str, org_id: str, plan: MMMPlan) -> DatasetResult:
    await validate_sources(pool, schema, plan)
    outputs = plan.output_names()
    spec = plan.preparation
    fetch_start = plan.date_start - timedelta(days=spec.history_days())
    by_day: dict[Any, dict[str, float | None]] = {}
    for source in plan.sources:
        names = list(source.metrics)
        metric_columns = [source.metrics[name] for name in names]
        text_columns = [source.metrics[name] for name in names if name in spec.text_to_numeric]
        rows = await catalog.get_daily_metric_rows(
            pool,
            schema,
            source.table,
            org_id,
            source.date_column,
            metric_columns,
            fetch_start,
            plan.date_end,
            filters=source.filters or None,
            text_columns=text_columns or None,
        )
        for row in rows:
            day_values = by_day.setdefault(row["date"], {})
            for name, value in zip(names, row["values"], strict=True):
                day_values[name] = float(value) if value is not None else None

    rows, log = build_rows(by_day, outputs, plan.kpi, plan.date_start, plan.date_end, spec)
    if len(rows) < MIN_ROWS:
        raise PlanError(f"only {len(rows)} usable rows in the window; at least {MIN_ROWS} are needed")
    columns = [DATE_COLUMN, *outputs, *spec.feature_names()]
    return DatasetResult(columns=columns, rows=rows, log=log)
