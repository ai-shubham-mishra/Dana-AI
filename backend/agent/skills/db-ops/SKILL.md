---
name: db-ops
description: Read the client's connector data directly with a read-only SQL query when the list and channel tools are not enough.
---

# Database operations

Use this domain to answer data questions the connector tools do not cover, such as the latest date in a connector, row counts by week, or a total for one channel. Start with `list_connectors` and `list_channels_within_connector` to learn the table and column names, then use `query_database` with one SELECT. Never ask the user for a date range or column name that these tools can discover.
