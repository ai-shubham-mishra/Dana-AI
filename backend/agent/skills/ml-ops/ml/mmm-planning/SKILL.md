---
name: mmm-planning
description: Plan and start a Marketing Mix Model training run on the org's connector data - collect the KPI and channels, map them to connector tables, resolve dates, then request approval through start_mmm_run.
---

# MMM planning and training

Use this skill when the user wants to build, run, or understand a Marketing Mix Model on their own data. Follow the `mmm` skill for the full recipe (data strategy, config, script, evaluation, run folder).

## Steps

1. Confirm the business KPI (for example revenue, conversions, or sign-ups) and its currency.
2. Ask which marketing channels to model (for example Meta Ads, Google Ads, TV, email).
3. Resolve the date range without asking: call `get_current_date`, then `resolve_date_range` with the user's phrase (for example "last 12 months"). Ask for dates only if `resolve_date_range` returns an error.
4. Discover the data with `list_connectors`, then `list_channels_within_connector` for each connector the user names. Its output also gives each date column's earliest and latest value, so do not query the database for those. Map each KPI, channel, and control to a connector table, date column, and metric column. Do not guess names. When the user's wording does not match a column exactly, call `find_connector_columns` with a regex (see the find-connector-columns skill). If the user limits the model to one country or market, find the stored values with `list_connector_column_values` (see `mmm-data-strategy` section 3a).
5. Follow `mmm-data-strategy` to check coverage, grain, and gaps. Propose controls from the connector columns (holiday or Black Friday flags, promotion or discount columns, price, weather). Ask the user with `ask_user` to confirm which ones to use, listing the candidates as options. Keep every control the user confirms; do not drop them later. Confirm the country or market scope in the same step.
6. Summarize the inputs, the controls, the scope, and your reasoning in a short list, then confirm with the user.
7. When the user asks to train, call `start_mmm_run` with the mapped `kpi`, `channels`, `controls`, `sources` (with the same `filters` on every source that carries the scope column), `date_start`, `date_end`, any whitelisted `overrides`, and a short `rationale`. Pass `controls_reason` only when the user confirmed that no controls apply. A human approves, edits, or rejects the plan first.
8. After submission, tell the user the run folder holds the dataset, config, training script, evaluation, and model, and that progress is on the Jobs tab.

## Boundaries

- Do not claim any results before a run has succeeded. Point the user to the Jobs tab for progress and output.
- Do not guess column names or values. Ask the user.
- Do not call `start_mmm_run` until the KPI, channels and controls are confirmed and a date range has been resolved.
- Never submit an empty `controls` list unless the user confirmed there are no controls, and then pass `controls_reason`.
- The legacy `start_training_job` tool only trains on the bundled sample dataset. Use `start_mmm_run` for client data.
