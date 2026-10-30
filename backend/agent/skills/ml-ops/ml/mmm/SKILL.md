---
name: mmm
description: End-to-end recipe for training a Marketing Mix Model on the client's own connector data. Covers data strategy, config, the generated training script, evaluation, and the run folder. Start here before any MMM work.
---

# MMM training recipe

Use this recipe whenever the user wants a Marketing Mix Model (MMM), channel attribution, budget response curves, or "what drives our sales". Work like a careful data scientist: reason from the client's real tables, state assumptions, and let the numbers decide.

## Workflow

1. **Understand the business question.** Confirm the KPI (for example revenue, conversions, sign-ups), its currency, and the decision it will support (budget split, forecasting, planning). See [data-strategy](../data-strategy/SKILL.md).
2. **Discover the data.** Call `list_connectors`, then `list_channels_within_connector` for each connector the user names. To match the user's wording to real column names, call `find_connector_columns` with a regex. Only org-scoped tables can be used for training. Shared tables are reference data only. If the user limits the model to one country or market, call `list_connector_column_values` on that column for each table (see [data-strategy](../data-strategy/SKILL.md) section 3a).
3. **Build a data strategy.** Decide which table supplies the KPI, which supply channel spend, which are controls (seasonality, promotions, pricing, weather), the date window, and how to aggregate to one row per date. Write the reasoning down in plain language for the user.
4. **Check the plan against the data.** Read each connector's earliest and latest dates from `list_channels_within_connector` (no SQL needed for these). Call `get_current_date` and `resolve_date_range` for the window. Do not ask the user for dates unless the tool errors.
5. **Prepare the data.** Call `profile_connector_columns` on the KPI, channel, and control columns. Any text column that holds numbers goes in `preparation.text_to_numeric`. Decide the calendar features, holiday country, lags, and rolling means, following [data-preparation](./data-preparation/SKILL.md). Call `preview_mmm_dataset` with the same plan and check the row count, dropped days, and blanks before you go on.
6. **Choose the configuration.** Start from the defaults in [config-reference](../config-reference/SKILL.md). Only override a value when you can justify it from the data (for example fewer draws for a quick check, a shorter adstock for weekly data).
7. **Request the run.** Confirm controls, the country or market scope, and the preparation choices with the user first (see data-strategy sections 3 and 3a). Call `start_mmm_run` with the sources (with `filters` for the scope), KPI, channels, controls, date range, overrides, `preparation`, and a `rationale` that explains the strategy. Pass `controls_reason` only when no controls apply. A human approves, edits, or rejects it first.
8. **Explain the outcome.** When the job finishes, read the evaluation (see [evaluation](../evaluation/SKILL.md)) and report convergence, fit, and any excluded channels. Never claim results before a job has succeeded.

## What happens when a run starts

For every run, the platform does the following. Do not bypass it.

- Builds `dataset.csv` from the connector tables for the signed-in org only. It applies the approved `preparation`: text numbers are read, blanks become 0, and calendar, holiday, lag, and rolling features are added.
- Writes `dataset_log.json` with the plan, row counts, dropped days, blanks filled per output, and the feature list.
- Writes `config.yml` from the defaults plus the approved overrides.
- Generates `train.py` on the fly from the template in [run-script](../run-script/SKILL.md). The script is not hand-written per client.
- Executes `train.py` in a sandboxed subprocess inside the run folder. The sandbox gets a minimal environment with no secrets.
- Writes `evaluation.json` and `mmm_model.nc` into the same run folder.

The run folder is `var/training/<job_id>/` and always holds all six files: `dataset.csv`, `dataset_log.json`, `config.yml`, `train.py`, `evaluation.json`, `mmm_model.nc`. A run is marked successful only when all six exist.

## Boundaries

- Only use columns and tables the catalog reports. Do not invent names.
- Do not train on shared (non-org-scoped) tables.
- Do not submit a run until the KPI, channels, and date range are confirmed.
- Keep the rationale honest. If the data is too short, too sparse, or a channel has no spend, say so and exclude it rather than forcing it through.
