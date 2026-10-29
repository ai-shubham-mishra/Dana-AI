import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.system_ops.calendar.common import DEFAULT_TIMEZONE, resolve_zone, today_in

EXPLICIT_RANGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})$")
RELATIVE_RANGE = re.compile(r"^(?:last|past)\s+(\d{1,3})\s+(day|week|month|quarter|year)s?$")
UNIT_MONTHS = {"month": 1, "quarter": 3, "year": 12}
SUPPORTED = (
    "'last N days', 'last N weeks', 'last N months', 'last N quarters', 'last N years', "
    "'this week', 'last week', 'this month', 'last month', 'month to date', "
    "'this quarter', 'last quarter', 'quarter to date', 'this year', 'last year', 'year to date', "
    "or an explicit 'YYYY-MM-DD to YYYY-MM-DD'"
)


def _quarter_start(day: date) -> date:
    return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)


def resolve_range(phrase: str, today: date) -> tuple[date, date]:
    """Turn a plain-English date phrase into an inclusive (start, end) pair ending on or before today."""
    raw = phrase.strip()
    explicit = EXPLICIT_RANGE.match(raw)
    if explicit:
        start, end = date.fromisoformat(explicit.group(1)), date.fromisoformat(explicit.group(2))
        if start > end:
            raise ValueError("The start date is after the end date.")
        return start, end

    text = " ".join(raw.lower().replace("-", " ").split())
    relative = RELATIVE_RANGE.match(text)
    if relative:
        count, unit = int(relative.group(1)), relative.group(2)
        if unit == "day":
            return today - timedelta(days=count), today
        if unit == "week":
            return today - timedelta(weeks=count), today
        return today - relativedelta(months=UNIT_MONTHS[unit] * count), today

    first_of_month = today.replace(day=1)
    first_of_year = date(today.year, 1, 1)
    this_quarter = _quarter_start(today)
    this_monday = today - timedelta(days=today.weekday())
    last_month_end = first_of_month - timedelta(days=1)
    last_quarter_end = this_quarter - timedelta(days=1)
    fixed = {
        "this week": (this_monday, today),
        "last week": (this_monday - timedelta(weeks=1), this_monday - timedelta(days=1)),
        "this month": (first_of_month, today),
        "month to date": (first_of_month, today),
        "last month": (last_month_end.replace(day=1), last_month_end),
        "this quarter": (this_quarter, today),
        "quarter to date": (this_quarter, today),
        "last quarter": (_quarter_start(last_quarter_end), last_quarter_end),
        "this year": (first_of_year, today),
        "year to date": (first_of_year, today),
        "ytd": (first_of_year, today),
        "last year": (date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)),
    }
    if text in fixed:
        return fixed[text]
    raise ValueError(f"Cannot resolve '{phrase}'. Supported phrases: {SUPPORTED}.")


class ResolveDateRangeInput(ToolInput):
    phrase: str = Field(
        description="A date phrase such as 'last 12 months', 'this year', 'last quarter', or an explicit 'YYYY-MM-DD to YYYY-MM-DD'."
    )
    timezone: str = Field(
        default=DEFAULT_TIMEZONE,
        description="IANA timezone that defines 'today', for example 'UTC' or 'Asia/Kolkata'. Use the user's timezone when it is known.",
    )


class ResolveDateRangeTool(BaseTool):
    name: str = "resolve_date_range"
    description: str = (
        "Convert a relative date phrase such as 'last 12 months' or 'this year' into an exact range "
        "in the form 'YYYY-MM-DD to YYYY-MM-DD'. Use the result as a date_range value instead of asking the user for dates."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ResolveDateRangeInput

    async def execute(self, phrase: str, timezone: str = DEFAULT_TIMEZONE) -> ToolOutput:
        try:
            today = today_in(resolve_zone(timezone))
            start, end = resolve_range(phrase, today)
        except ValueError as exc:
            return ToolOutput(success=False, error=str(exc))
        return ToolOutput(
            result=f"{start.isoformat()} to {end.isoformat()}",
            metadata={"start_date": start.isoformat(), "end_date": end.isoformat(), "today": today.isoformat()},
        )
