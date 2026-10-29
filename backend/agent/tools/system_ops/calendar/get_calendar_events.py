from datetime import date, timedelta
from typing import Callable, Literal

import holidays
from dateutil.easter import easter
from dateutil.relativedelta import SU, TH, relativedelta
from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.system_ops.calendar.common import DEFAULT_TIMEZONE, resolve_zone, today_in

MAX_YEAR_SPAN = 10


def _nth_weekday(year: int, month: int, weekday, n: int) -> date:
    return date(year, month, 1) + relativedelta(weekday=weekday(n))


def _black_friday(year: int) -> date:
    return _nth_weekday(year, 11, TH, 4) + timedelta(days=1)


# (name, date rule, countries where it applies or None for all)
RETAIL_EVENTS: list[tuple[str, Callable[[int], date], set[str] | None]] = [
    ("Valentine's Day", lambda y: date(y, 2, 14), None),
    ("Mother's Day", lambda y: _nth_weekday(y, 5, SU, 2), {"US", "CA", "DE", "AT", "CH", "CZ"}),
    ("Mothering Sunday", lambda y: easter(y) - timedelta(days=21), {"GB"}),
    ("Father's Day", lambda y: _nth_weekday(y, 6, SU, 3), {"US", "CA", "GB"}),
    ("Singles' Day", lambda y: date(y, 11, 11), None),
    ("Black Friday", _black_friday, None),
    ("Cyber Monday", lambda y: _black_friday(y) + timedelta(days=3), None),
]


def _retail_events(country: str, years: list[int]) -> dict[date, str]:
    events: dict[date, str] = {}
    for year in years:
        for name, rule, countries in RETAIL_EVENTS:
            if countries is None or country in countries:
                events[rule(year)] = name
    return events


class GetCalendarEventsInput(ToolInput):
    country: str = Field(description="ISO 3166-1 alpha-2 country code, for example 'US', 'IN', 'GB', 'DE'.")
    subdivision: str | None = Field(
        default=None, description="Optional state or region code, for example 'CA' for California in the US."
    )
    start_date: str | None = Field(
        default=None, description="First day to list, YYYY-MM-DD. Defaults to 1 January of the current year."
    )
    end_date: str | None = Field(
        default=None,
        description=f"Last day to list, YYYY-MM-DD. Defaults to 31 December of the current year. At most {MAX_YEAR_SPAN} years after start_date.",
    )
    event_type: Literal["all", "public_holiday", "retail"] = Field(
        default="all", description="'public_holiday' for official holidays, 'retail' for shopping dates, or 'all'."
    )
    timezone: str | None = Field(
        default=None,
        description="IANA timezone that defines the current year, for example 'Asia/Kolkata'. Leave empty to use the user's own timezone.",
    )


class GetCalendarEventsTool(BaseTool):
    name: str = "get_calendar_events"
    description: str = (
        "List public holidays and retail dates (Black Friday, Mother's Day, and so on) for a country and date window. "
        "Use it when a holiday or seasonal event may affect marketing or sales data."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return GetCalendarEventsInput

    async def execute(
        self,
        country: str,
        subdivision: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        event_type: str = "all",
        timezone: str | None = None,
    ) -> ToolOutput:
        try:
            country = country.strip().upper()
            year = today_in(resolve_zone(timezone)).year
            start = date.fromisoformat(start_date) if start_date else date(year, 1, 1)
            end = date.fromisoformat(end_date) if end_date else date(year, 12, 31)
        except ValueError as exc:
            return ToolOutput(success=False, error=f"Invalid date or timezone: {exc}")
        if start > end:
            return ToolOutput(success=False, error="start_date is after end_date.")
        if end.year - start.year > MAX_YEAR_SPAN:
            return ToolOutput(success=False, error=f"The window is longer than {MAX_YEAR_SPAN} years. Split it into smaller ranges.")

        years = list(range(start.year, end.year + 1))
        found: dict[date, str] = {}
        if event_type in ("all", "public_holiday"):
            try:
                calendar = holidays.country_holidays(country, subdiv=subdivision, years=years)
            except NotImplementedError:
                return ToolOutput(success=False, error=f"No holiday calendar is available for '{country}'" + (f" / '{subdivision}'." if subdivision else "."))
            for day, name in calendar.items():
                found[day] = f"{name} (public holiday)"
        if event_type in ("all", "retail"):
            for day, name in _retail_events(country, years).items():
                found.setdefault(day, f"{name} (retail)")

        in_window = sorted((day, label) for day, label in found.items() if start <= day <= end)
        if not in_window:
            return ToolOutput(result=f"No {event_type} events for {country} between {start} and {end}.")
        lines = [f"{day.isoformat()} {day:%a} {label}" for day, label in in_window]
        return ToolOutput(result="\n".join(lines), metadata={"count": len(lines), "country": country})
