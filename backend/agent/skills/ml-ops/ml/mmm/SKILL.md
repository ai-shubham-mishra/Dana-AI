---
name: mmm
description: End-to-end recipe for training a Marketing Mix Model on the client's own connector data. Covers data strategy, config, the generated training script, evaluation, and the run folder. Start here before any MMM work.
---

# MMM training recipe

Use this recipe whenever the user wants a Marketing Mix Model (MMM), channel attribution, budget response curves, or "what drives our sales". Work like a careful data scientist: reason from the client's real tables, state assumptions, and let the numbers decide.

## Workflow

1. **Understand the business question.** Confirm the KPI (for example revenue, conversions, sign-ups), its currency, and the decision it will support (budget split, forecasting, planning). See [data-strategy](../data-strategy/SKILL.md).
2. **Discover the data.** Call `list_connectors`, then `list_channels_within_connector` for each connector the user names. Only org-scoped tables can be used for training. Shared tables are reference data only.
3. **Build a data strategy.** Decide which table supplies the KPI, which supply channel spend, which are controls (seasonality, promotions, pricing, weather), the date window, and how to aggregate to one row per date. Write the reasoning down in plain language for the user.
4. **Check the plan against the data.** Read each connector's earliest and latest dates from `list_channels_within_connector` (no SQL needed for these). Call `get_current_date` and `resolve_date_range` for the window. Do not ask the user for dates unless the tool errors.
5. **Choose the configuration.** Start from the defaults in [config-reference](../config-reference/SKILL.md). Only override a value when you can justify it from the data (for example fewer draws for a quick check, a shorter adstock for weekly data).
6. **Request the run.** Call `start_mmm_run` with the sources, KPI, channels, controls, date range, overrides, and a `rationale` that explains the strategy. A human approves, edits, or rejects it first.
7. **Explain the outcome.** When the job finishes, read the evaluation (see [evaluation](../evaluation/SKILL.md)) and report convergence, fit, and any excluded channels. Never claim results before a job has succeeded.

## What happens when a run starts

For every run, the platform does the following. Do not bypass it.

- Builds `dataset.csv` from the connector tables for the signed-in org only.
- Writes `config.yml` from the defaults plus the approved overrides.
- Generates `train.py` on the fly from the template in [run-script](../run-script/SKILL.md). The script is not hand-written per client.
- Executes `train.py` in a sandboxed subprocess inside the run folder. The sandbox gets a minimal environment with no secrets.
- Writes `evaluation.json` and `mmm_model.nc` into the same run folder.

The run folder is `var/training/<job_id>/` and always holds all five files: `dataset.csv`, `config.yml`, `train.py`, `evaluation.json`, `mmm_model.nc`. A run is marked successful only when all five exist.

## Boundaries

- Only use columns and tables the catalog reports. Do not invent names.
- Do not train on shared (non-org-scoped) tables.
- Do not submit a run until the KPI, channels, and date range are confirmed.
- Keep the rationale honest. If the data is too short, too sparse, or a channel has no spend, say so and exclude it rather than forcing it through.
