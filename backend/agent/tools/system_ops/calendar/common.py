from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent.request_context import client_timezone

DEFAULT_TIMEZONE = "UTC"


def resolve_zone(name: str | None) -> ZoneInfo:
    name = name or client_timezone() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone '{name}'. Use an IANA name such as 'UTC' or 'Asia/Kolkata'.") from exc


def today_in(zone: ZoneInfo) -> date:
    return datetime.now(zone).date()
