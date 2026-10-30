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
4. Discover the data with `list_connectors`, then `list_channels_within_connector` for each connector the user names. Map each KPI, channel, and control to a connector table, date column, and metric column. Do not guess names.
5. Follow `mmm-data-strategy` to check coverage, grain, and gaps. Summarize the inputs and your reasoning in a short list, then confirm with the user.
6. When the user asks to train, call `start_mmm_run` with the mapped `kpi`, `channels`, `controls`, `sources`, `date_start`, `date_end`, any whitelisted `overrides`, and a short `rationale`. A human approves, edits, or rejects the plan first.
7. After submission, tell the user the run folder holds the dataset, config, training script, evaluation, and model, and that progress is on the Jobs tab.

## Boundaries

- Do not claim any results before a run has succeeded. Point the user to the Jobs tab for progress and output.
- Do not guess column names or values. Ask the user.
- Do not call `start_mmm_run` until the KPI and channels are confirmed and a date range has been resolved.
- The legacy `start_training_job` tool only trains on the bundled sample dataset. Use `start_mmm_run` for client data.
