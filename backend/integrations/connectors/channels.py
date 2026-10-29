from collections.abc import Iterable
from typing import Any

from psycopg_pool import AsyncConnectionPool

from integrations.connectors.catalog import ORG_COLUMN, count_org_rows, get_connector_columns

# Channel columns are named <Channel>_<metric>, e.g. GAds-PMax_spend or TV_GRP.
CHANNEL_METRICS = frozenset({"spend", "impressions", "impr", "clicks", "views", "grp", "reach"})


def split_channel_column(column: str) -> tuple[str, str] | None:
    channel, separator, metric = column.rpartition("_")
    if not separator or not channel or metric.lower() not in CHANNEL_METRICS:
        return None
    return channel, metric


def derive_channels(column_names: Iterable[str]) -> list[dict[str, Any]]:
    channels: dict[str, dict[str, Any]] = {}
    for column in column_names:
        parsed = split_channel_column(column)
        if parsed is None:
            continue
        channel, metric = parsed
        entry = channels.setdefault(channel, {"name": channel, "metrics": [], "columns": []})
        entry["metrics"].append(metric)
        entry["columns"].append(column)
    return list(channels.values())


async def describe_connector(
    pool: AsyncConnectionPool, schema: str, connector: str, org_id: str
) -> dict[str, Any] | None:
    columns = await get_connector_columns(pool, schema, connector)
    if columns is None:
        return None
    names = [column["name"] for column in columns]
    org_scoped = ORG_COLUMN in names
    return {
        "connector": connector,
        "org_scoped": org_scoped,
        "org_rows": await count_org_rows(pool, schema, connector, org_id) if org_scoped else None,
        "channels": derive_channels(names),
    }


def format_channels(described: dict[str, Any]) -> str:
    if described["org_scoped"]:
        lines = [f"Connector {described['connector']} has {described['org_rows']} rows for this organization."]
        if described["org_rows"] == 0:
            lines.append("This organization has no rows in this connector, so it cannot be modelled from it.")
    else:
        lines = [f"Connector {described['connector']} is a shared table with no org_id column."]
    channels = described["channels"]
    if not channels:
        lines.append(
            "No channel columns were found. Channel columns are named <Channel>_<metric>, "
            "with metric spend, impressions, impr, clicks, views, grp or reach."
        )
        return "\n".join(lines)
    lines.append(f"Channels ({len(channels)}):")
    for channel in channels:
        lines.append(f"- {channel['name']}: {', '.join(channel['metrics'])}")
    return "\n".join(lines)
