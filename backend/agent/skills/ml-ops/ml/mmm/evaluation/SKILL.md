---
name: evaluation
description: How to read an MMM run's evaluation - sampler health (divergences, R-hat), data coverage, excluded channels - and what to tell the user when a run passes or fails.
---

# MMM evaluation

Every run writes `evaluation.json` into its run folder. Read it before reporting results.

## Fields

- `status`: `success` when sampling finished and all six run files exist.
- `rows`, `date_start`, `date_end`: the training window the model was fit on, after aggregation. With a holdout these exclude the held-out rows.
- `validation`: the split. `holdout_periods` is the number of held-out rows, and `train_rows`, `train_start`, `train_end`, `holdout_rows`, `holdout_start`, `holdout_end` give the two windows. `holdout_rows` is 0 when `holdout_periods` is 0.
- `channels`, `controls`: what the model used.
- `excluded_channels`: channels dropped for having too little spend. Always mention these.
- `divergences`: sampler divergences. Must be 0 for a trusted result.
- `max_rhat`: largest R-hat across the key parameters. Must be at most 1.1.
- `rhat_ok`: true when `max_rhat` is at most 1.1.
- `sampling`: the chains, tune, draws, target accept and seed used.
- `fit`: accuracy against the training window (in-sample, see below). Keys:
  - `r2`: share of variance explained. Above 0.6 is a reasonable fit for weekly marketing data.
  - `mae`, `rmse`, `bias`: error in target units. `bias` is mean(actual − predicted), so positive means the model under-predicts. Near 0 means no systematic drift.
  - `mape_pct`, `wmape_pct`: percentage errors. `wmape_pct` weights big weeks more and is the headline accuracy number.
  - `hdi94_coverage_pct`, `hdi50_coverage_pct`: share of actuals inside the 94% and 50% posterior bands. Near 94 and 50 means the uncertainty is honest. Much lower means overconfident.
  - `durbin_watson`: near 2 means no autocorrelation left in the residuals. Below 1.5 or above 2.5 means the model is missing a time pattern.
  - `shapiro_wilk_p`: above 0.05 means residuals look normal.
  - `residual_trend_p`: above 0.05 means residuals show no drift over time.
  - `breusch_pagan_p`: above 0.05 means residual variance is stable (no heteroscedasticity).
  - `worst_residuals`: the five weeks the model missed most, with actual, predicted and `error_pct`. Check whether they line up with a known event such as a promotion, outage or holiday.
- `holdout`: out-of-sample accuracy on the last `validation.holdout_periods` rows, which the model never saw during fitting. It has the same keys as `fit`, and is `null` when the holdout is off. Its predictions are generated from the fitted model with the training tail carried in for adstock continuity. Compare it with `fit`:
  - `wmape_pct` on the holdout is the headline out-of-sample error.
  - A holdout `r2` close to the `fit` `r2` means the model generalises. A holdout `r2` far below the fit points to overfitting.
  - A negative holdout `r2` means the model predicts the holdout worse than its average. Say so plainly.
- `contributions`: `predicted_total` plus the total and share of each channel, control, intercept and yearly seasonality.
- `roas`: contribution over spend per channel. Keyed by `all_time`, `yearly` and `monthly`. Each channel has `mean`, `hdi_low_90`, `hdi_high_90` (or a list per period for yearly and monthly).
- `incremental_roas`: incremental contribution (counterfactual with zero spend) over spend, same shape as `roas`. In pymc-marketing 1.0 this equals `roas`, so the two can match exactly. Report it as one number and do not present it as a separate finding.
- `marginal_roas`: return on the next unit of spend at current levels, same shape. Lower than `roas` means diminishing returns, so use it for budget moves.
- `transformations`: posterior of `adstock_alpha` (carry-over), `saturation_lam` and `saturation_beta` (diminishing returns) per channel, and `gamma_control` per control.
- `metric_errors`: metrics that failed to compute, keyed by name. An empty object means every metric succeeded. If it is not empty, say which metric is missing and do not invent a value for it.

## How to judge a run

- **Trusted:** divergences = 0, `rhat_ok` = true, and the fit is reasonable (`r2` above about 0.6, `hdi94_coverage_pct` between roughly 85 and 100, no `metric_errors`). When a holdout exists, its `r2` is positive and its `wmape_pct` is within about 5 points of the fit `wmape_pct`. Report the channel contributions, ROAS and the diminishing-returns picture.
- **Usable with caveats:** divergences small (under 1 percent of draws), R-hat slightly above 1.1, or a weak fit (low `r2`, coverage far from 94, residual autocorrelation or trend). Say the estimates are less certain and name the weak metric. Suggest more tuning, a longer window, or a missing driver.
- **Not trusted:** many divergences or R-hat well above 1.1. Do not present channel contributions as facts. Propose one concrete fix (more tuning, a shorter adstock, dropping a collinear channel, or a longer window) and ask before rerunning.

## What to tell the user

- The window and row count, and which channels and controls were used.
- Any excluded channels and why.
- Whether the sampler converged, in one sentence.
- Where the model and run folder are, and that the Jobs tab shows the full history.

Do not claim ROI or budget recommendations beyond what the evaluation supports. Report the holdout `wmape_pct` and `r2` next to the in-sample `fit` numbers, and describe the in-sample numbers as "fit to the data used". Say plainly that the saved model was fit without the holdout weeks, and that a final all-data fit is possible once the holdout check passes.
