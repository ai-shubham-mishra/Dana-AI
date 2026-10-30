---
name: resolve-date-range
description: Convert a phrase such as 'last 12 months' or 'this year' into an exact 'YYYY-MM-DD to YYYY-MM-DD' range.
---

# resolve_date_range

Use the returned range as the `date_range` value for training. Supported phrases: "last N days/weeks/months/quarters/years", "this week", "last week", "this month", "last month", "month to date", "this quarter", "last quarter", "quarter to date", "this year", "last year", "year to date", or an explicit range. Ask the user only when the tool returns an error.
