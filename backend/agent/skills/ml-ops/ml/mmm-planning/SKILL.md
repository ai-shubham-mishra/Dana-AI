---
name: mmm-planning
description: Plan and start a Marketing Mix Model training run on the org's connector data - collect the KPI and channels, map them to connector tables, resolve dates, then request approval through start_mmm_run.
---

# MMM planning and training

Use this skill when the user wants to build, run, or understand a Marketing Mix Model on their own data. Follow the `mmm` skill for the full recipe (data strategy, config, script, evaluation, run folder).

## Steps

1. Confirm the business KPI (for example revenue, conversions, or sign-ups) and its currency.
2. Ask which marketing channels to model (for example Meta Ads, Google Ads, TV, email).
3. Ask the training window every time, before any training plan is built, even when the user already named a period. Follow the "Training window" section below.
4. Ask for a model name (see "Model name" below).
5. Discover the data with `list_connectors`, then `list_channels_within_connector` for each connector the user names. Its output also gives each date column's earliest and latest value, so do not query the database for those. Map each KPI, channel, and control to a connector table, date column, and metric column. Do not guess names. When the user's wording does not match a column exactly, call `find_connector_columns` with a regex (see the find-connector-columns skill). If the user limits the model to one country or market, find the stored values with `list_connector_column_values` (see `data-strategy` section 3a).
6. Follow `data-strategy` to check coverage, grain, and gaps. Propose controls from the connector columns (holiday or Black Friday flags, promotion or discount columns, price, weather). Ask the user with `ask_user` to confirm which ones to use, listing the candidates as options. Keep every control the user confirms; do not drop them later. Confirm the country or market scope in the same step.
7. Summarize the inputs, the controls, the scope, the model name, and your reasoning in a short list, then confirm with the user.
8. When the user asks to train, call `start_mmm_run` with `model_name` (the confirmed name) for a new model, or `model_id` (the existing model's id) when retraining it with new settings, the mapped `kpi`, `channels`, `controls`, `sources` (with the same `filters` on every source that carries the scope column), `date_start` and `date_end` from the window the user chose, any whitelisted `overrides`, and a short `rationale` that names the chosen window. Pass `controls_reason` only when the user confirmed that no controls apply. A human approves, edits, or rejects the plan first.
9. After submission, tell the user the run folder holds the dataset, config, training script, evaluation, and model, and that progress is on the Jobs tab.

## Model name

Every new training needs a model name that no other model of the user uses (the match ignores case). Before asking:

1. Call `list_model_versions` with no `model_id` to list the user's existing model names.
2. Ask the user for a name with a `text` question, and suggest a descriptive one (for example "Revenue Q1 MMM"). Do not reuse an existing name.
3. If `start_mmm_run` returns that the name is taken, it lists suggested names with hex suffixes. Ask the user to pick one with `single_select` (offer the suggestions plus "Type my own"), then submit again with the chosen name.

Retraining an existing model keeps its name and does not need one. Retraining with new settings means passing that model's `model_id` to `start_mmm_run`, which adds a new version to it. Never leave `model_id` empty for an existing model, because that creates a second model. Find the `model_id` with `list_model_versions`, and ask the user which model to retrain if it is unclear. Also ask the user the training window before every training, including retrains, using the suggestions in "Training window" below.

## Training window

Always ask the training window before `start_mmm_run`, even if the user already said a period (for example "train on last year"). Ask one `single_select` question with `ask_user` and these suggestions:

- Last 12 weeks
- Last 6 months
- Last 12 months
- Last 2 years
- Full history (from the earliest date in the data)

If none fits, ask a `text` question for the window in weeks, months or years, or "full history". Then build the dates:

- For "last N weeks/months/years", call `resolve_date_range` with that phrase.
- For full history, use the earliest and latest dates that `list_channels_within_connector` shows for the connector's date column. Set `date_start` to the earliest date and `date_end` to the latest date.

Use the resulting dates as `date_start` and `date_end`, and mention the chosen window in the plan summary before submitting.

## Boundaries

- Do not claim any results before a run has succeeded. Point the user to the Jobs tab for progress and output.
- Do not guess column names or values. Ask the user.
- Do not call `start_mmm_run` until the KPI, channels, controls, model name and training window are confirmed.
- Never submit an empty `controls` list unless the user confirmed there are no controls, and then pass `controls_reason`.
- The legacy `start_training_job` tool only trains on the bundled sample dataset. Use `start_mmm_run` for client data.
