---
name: profile-connector-columns
description: Profile connector columns before modelling - blanks, how many values read as numbers, unreadable samples, and a recommendation for numeric, text-as-number, mixed or non-numeric columns.
---

# profile_connector_columns

Call this with `connector` and an explicit list of `columns` (up to 20) once you know the names from `find_connector_columns`. It reads the column in SQL and reports, per column:

- `rows`, `blank`, and the min, max and sum where they apply.
- `readable_as_number` and `unreadable`. Parsing removes spaces, commas and currency signs, so `"1,234.50"` and `"$ 99"` count as numbers.
- `unreadable_samples`: up to five values that could not be read.
- `recommendation`: one of numeric, text holding numbers, mixed, mostly non-numeric, or empty.

It is read-only and needs no approval. Use its recommendation as a starting point and check the samples before you decide. A text column that holds numbers must be declared in `preparation.text_to_numeric` when you call `start_mmm_run`. See the `data-preparation` skill for the full decision rules.
