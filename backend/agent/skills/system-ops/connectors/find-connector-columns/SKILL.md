---
name: find-connector-columns
description: Find a connector's columns by a case-insensitive regular expression, so the user's wording matches the real column names.
---

# find_connector_columns

Column names differ per org and can contain hyphens or different casing, for example `GAds-Demand-Gen_spend`. Do not guess them. Call this with `connector` and a `pattern` built from the user's words, such as `gads.*demand` or `spend|cost`. It is read-only and needs no approval.

If nothing matches, the output lists the connector's columns (or asks for a broader pattern when there are many). Pick the column that fits, and confirm the choice with the user when it is unclear. Use the exact name it returns in any plan or source spec.
