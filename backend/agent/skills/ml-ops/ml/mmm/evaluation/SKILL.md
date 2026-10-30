---
name: mmm-evaluation
description: How to read an MMM run's evaluation - sampler health (divergences, R-hat), data coverage, excluded channels - and what to tell the user when a run passes or fails.
---

# MMM evaluation

Every run writes `evaluation.json` into its run folder. Read it before reporting results.

## Fields

- `status`: `success` when sampling finished and all five run files exist.
- `rows`, `date_start`, `date_end`: the window actually used after aggregation.
- `channels`, `controls`: what the model used.
- `excluded_channels`: channels dropped for having too little spend. Always mention these.
- `divergences`: sampler divergences. Must be 0 for a trusted result.
- `max_rhat`: largest R-hat across the key parameters. Must be at most 1.1.
- `rhat_ok`: true when `max_rhat` is at most 1.1.
- `sampling`: the chains, tune, draws, target accept and seed used.
- `fit`: accuracy against the training data (in-sample, see below). Keys:
  - `r2`: share of variance explained. Above 0.6 is a reasonable fit for weekly marketing data.
  - `mae`, `rmse`, `bias`: error in target units. `bias` is mean(actual − predicted), so positive means the model under-predicts. Near 0 means no systematic drift.
  - `mape_pct`, `wmape_pct`: percentage errors. `wmape_pct` weights big weeks more and is the headline accuracy number.
  - `hdi94_coverage_pct`, `hdi50_coverage_pct`: share of actuals inside the 94% and 50% posterior bands. Near 94 and 50 means the uncertainty is honest. Much lower means overconfident.
  - `durbin_watson`: near 2 means no autocorrelation left in the residuals. Below 1.5 or above 2.5 means the model is missing a time pattern.
  - `shapiro_wilk_p`: above 0.05 means residuals look normal.
  - `residual_trend_p`: above 0.05 means residuals show no drift over time.
  - `breusch_pagan_p`: above 0.05 means residual variance is stable (no heteroscedasticity).
  - `worst_residuals`: the five weeks the model missed most, with actual, predicted and `error_pct`. Check whether they line up with a known event such as a promotion, outage or holiday.
- `contributions`: `predicted_total` plus the total and share of each channel, control, intercept and yearly seasonality.
- `roas`: contribution over spend per channel. Keyed by `all_time`, `yearly` and `monthly`. Each channel has `mean`, `hdi_low_90`, `hdi_high_90` (or a list per period for yearly and monthly).
- `incremental_roas`: incremental contribution (counterfactual with zero spend) over spend, same shape as `roas`. In pymc-marketing 1.0 this equals `roas`, so the two can match exactly. Report it as one number and do not present it as a separate finding.
- `marginal_roas`: return on the next unit of spend at current levels, same shape. Lower than `roas` means diminishing returns, so use it for budget moves.
- `transformations`: posterior of `adstock_alpha` (carry-over), `saturation_lam` and `saturation_beta` (diminishing returns) per channel, and `gamma_control` per control.
- `metric_errors`: metrics that failed to compute, keyed by name. An empty object means every metric succeeded. If it is not empty, say which metric is missing and do not invent a value for it.

## How to judge a run

- **Trusted:** divergences = 0, `rhat_ok` = true, and the fit is reasonable (`r2` above about 0.6, `hdi94_coverage_pct` between roughly 85 and 100, no `metric_errors`). Report the channel contributions, ROAS and the diminishing-returns picture.
- **Usable with caveats:** divergences small (under 1 percent of draws), R-hat slightly above 1.1, or a weak fit (low `r2`, coverage far from 94, residual autocorrelation or trend). Say the estimates are less certain and name the weak metric. Suggest more tuning, a longer window, or a missing driver.
- **Not trusted:** many divergences or R-hat well above 1.1. Do not present channel contributions as facts. Propose one concrete fix (more tuning, a shorter adstock, dropping a collinear channel, or a longer window) and ask before rerunning.

## What to tell the user

- The window and row count, and which channels and controls were used.
- Any excluded channels and why.
- Whether the sampler converged, in one sentence.
- Where the model and run folder are, and that the Jobs tab shows the full history.

Do not claim ROI or budget recommendations beyond what the evaluation supports. Fit metrics are computed on the training window only (in-sample), so describe them as "fit to the data used", not as forecast accuracy. Say so if asked about out-of-sample accuracy; a holdout check is not part of this run yet.
