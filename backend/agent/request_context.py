from contextvars import ContextVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_TIMEZONE_LENGTH = 64

_client_timezone: ContextVar[str | None] = ContextVar("client_timezone", default=None)


def parse_client_timezone(value: str | None) -> str | None:
    if not value or len(value) > MAX_TIMEZONE_LENGTH:
        return None
    try:
        return ZoneInfo(value.strip()).key
    except (ZoneInfoNotFoundError, ValueError):
        return None


def bind_client_timezone(name: str | None) -> None:
    _client_timezone.set(name)


def client_timezone() -> str | None:
    return _client_timezone.get()
