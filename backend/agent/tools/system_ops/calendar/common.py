from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def resolve_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone '{name}'. Use an IANA name such as 'UTC' or 'Asia/Kolkata'.") from exc


def today_in(zone: ZoneInfo) -> date:
    return datetime.now(zone).date()
