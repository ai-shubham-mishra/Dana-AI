from datetime import datetime

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.system_ops.calendar.common import DEFAULT_TIMEZONE, resolve_zone


class GetCurrentDateInput(ToolInput):
    timezone: str = Field(
        default=DEFAULT_TIMEZONE,
        description="IANA timezone name, for example 'UTC' or 'Asia/Kolkata'. Use the user's timezone when it is known.",
    )


class GetCurrentDateTool(BaseTool):
    name: str = "get_current_date"
    description: str = (
        "Get today's date, weekday and current time in a timezone. "
        "Call it before resolving any relative date such as 'last 12 months' or 'this year'."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return GetCurrentDateInput

    async def execute(self, timezone: str = DEFAULT_TIMEZONE) -> ToolOutput:
        try:
            zone = resolve_zone(timezone)
        except ValueError as exc:
            return ToolOutput(success=False, error=str(exc))
        now = datetime.now(zone)
        result = (
            f"Today is {now:%Y-%m-%d} ({now:%A}). Current time {now:%H:%M} {timezone or DEFAULT_TIMEZONE}. "
            f"ISO timestamp: {now.isoformat(timespec='seconds')}."
        )
        return ToolOutput(result=result, metadata={"today": now.date().isoformat(), "timezone": timezone or DEFAULT_TIMEZONE})
