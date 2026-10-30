---
name: query-database
description: Run one read-only SQL SELECT over the client's connector tables to answer a data question on the fly.
---

# query_database

Run one PostgreSQL SELECT over the connector tables. Use it for questions like the latest date in a connector, the number of rows per week, or the total spend for a channel column.

- Do not use it for earliest or latest dates. `list_channels_within_connector` already shows them for every date column.
- Write one statement. Reads only. Writes, multiple statements, other schemas, and `pg_`/`information_schema` are refused.
- Aim for one or two queries per question, and never more than three.
- Connector tables are named as in `list_connectors`. Org-scoped tables are filtered to the signed-in organization for you, so do not add an `org_id` filter yourself.
- Results show at most 200 rows. Aggregate with `MAX`, `MIN`, `COUNT` or `SUM` when you need a summary.
- Date columns can be stored as text in `YYYY-MM-DD` form. Cast them with `::date` before comparing or taking the max.
- If the query fails, read the error, check the column names with `list_channels_within_connector`, and try again once before asking the user.
