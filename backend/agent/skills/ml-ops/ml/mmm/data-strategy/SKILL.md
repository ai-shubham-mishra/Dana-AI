---
name: mmm-data-strategy
description: How to turn a client's connector tables into an MMM dataset - choosing the KPI, channel spend, controls, date window, and aggregation, and checking the result before training.
---

# MMM data strategy

Reason through these steps before calling `start_mmm_run`. Write the answers down so the user can read the rationale on the approval card.

## 1. KPI

- The KPI is one numeric column that the business cares about, aggregated per date (for example `revenue`, `conversions`).
- Prefer a KPI that is a total, not a rate. Rates (CTR, ROAS) cannot be summed across channels.
- Choose a KPI from a table with `org_scoped = true`.

## 2. Channels

- A channel is one paid or owned marketing lever with a spend or investment series, for example `Meta-Ads_spend` or `GAds-PMax_spend`.
- Use spend (or impressions for reach-only channels) as the channel variable. Do not use clicks or conversions as channels, because they are outcomes, not inputs.
- Each channel must cover the same dates as the KPI. Missing dates are filled with 0 spend, which is correct only if the channel was actually off. If a channel started mid-window, say so in the rationale.
- Exclude a channel with no spend in the window. The trainer also drops channels below a minimal total spend.
- Keep channel names as stable, readable labels. Use the source connector and metric, for example `Meta_spend`.

## 3. Controls

Controls explain the KPI without being marketing spend. Good controls are:

- seasonality events (holidays, Black Friday flags)
- promotions or discount depth
- pricing changes
- weather or macro signals when the business is sensitive to them

Do not use the KPI itself, post-period outcomes, or variables that are only known after the fact as controls.

## 4. Date window

- Resolve the window with `get_current_date` and `resolve_date_range`.
- Prefer at least 2 years of weekly data (about 100 rows) or 1 year of daily data. Fewer than 20 rows is rejected by the trainer.
- Avoid windows that cut a campaign or a major event in half unless you state it.

## 5. Aggregation

- Each source table is aggregated to one row per date with `SUM` for every mapped column. Sum is correct for spend, impressions, and revenue. Do not average.
- Dates come from the `date_column` of each table. If a table has timestamps, the platform truncates them to dates.
- Multiple sources are joined on date. A date missing from one source gets 0 for that source's columns.

## 6. Checks before training

- Row count in the window is at least 20, and ideally at least 52 for weekly data. The trainer holds out the last `holdout_periods` rows (default 8) for an out-of-sample check and fits on the rest, so the training window needs at least 30 rows after the holdout. Daily data needs about 56 holdout rows, so size the window for the holdout too.
- The KPI has variance (not constant zero).
- Channels have non-zero spend in the window.
- No duplicated date rows after aggregation (the platform guarantees this, but say so if the source looks duplicated).
- Note any large gaps, outliers, or a sudden change in spend that the model cannot explain.

## 7. Report

State in plain language:

- the KPI and its source
- each channel, its source column, and any exclusions
- the controls and why each was included
- the date window and row count
- the risks that could bias the result (for example, a channel that launched recently)
