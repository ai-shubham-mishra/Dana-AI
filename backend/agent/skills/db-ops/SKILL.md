---
name: db-ops
description: Read the client's connector data directly with a read-only SQL query when the list and channel tools are not enough.
---

# Database operations

Use this domain to answer data questions the connector tools do not cover, such as row counts by week or a total for one channel. Start with `list_connectors` and `list_channels_within_connector` to learn the table and column names, then use `query_database` with one SELECT. Never ask the user for a date range or column name that these tools can discover.

- Earliest and latest dates per column are already in the `list_channels_within_connector` output. Never run `query_database` to find them, and never query for a connector's date range.
- Use `query_database` only for numbers those tools do not show, such as totals, weekly counts, or a single channel's sum.
- Use at most three `query_database` calls to answer one question. If the answer is still not clear, tell the user what you found and ask, instead of running more queries.
