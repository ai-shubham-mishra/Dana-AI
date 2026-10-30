---
name: mmm-config-reference
description: Reference for every MMM training setting - adstock, seasonality, priors, sampling - with the defaults and which ones the agent may override in a run request.
---

# MMM configuration reference

The defaults live in [defaults.yaml](./defaults.yaml). The platform writes the final `config.yml` into the run folder every time, so the exact settings are always reproducible.

## Settings the agent may override

Pass these as `overrides` on `start_mmm_run`. Anything else is rejected.

| Override key | Default | Allowed | Use it when |
|---|---|---|---|
| `adstock_l_max` | 10 | 1 to 52 | Weekly data: 4 to 8 for short carryover, up to 12 for long. Daily data: much larger. |
| `yearly_seasonality` | 2 | 0 to 6 | Set 0 for less than a year of data. |
| `time_varying_intercept` | false | true or false | Set true only with at least two years of data and a visible baseline drift. |
| `chains` | 4 | 1 to 8 | Lower for a quick check, keep 4 for the real run. |
| `tune` | 2000 | 100 to 4000 | Lower for a quick check. |
| `draws` | (sampler default) | 100 to 4000 | Lower for a quick check. |

Keep the default `random_seed` (123) so runs are comparable.

## Settings that are fixed by the recipe

These are part of the recipe and are not overridable from a run request:

- `target_accept` 0.95
- `random_seed` 123
- Priors listed below, except that `saturation_beta` sigma is always derived from each channel's share of spend.

## Priors

| Parameter | Prior | Why |
|---|---|---|
| intercept | HalfNormal(sigma 0.5) | Baseline sales are positive. |
| saturation_beta | HalfNormal, sigma = spend share | Channels with more spend can have larger effects. |
| saturation_lam | Gamma(3, 1) | Keeps diminishing returns in a sensible range. |
| adstock_alpha | Beta(1, 3) | Most carryover is short. |
| gamma_control | Normal(0, 0.05) | Controls are weak unless the data says otherwise. |
| gamma_fourier | Laplace(0, 0.1) | Sparse seasonality. |
| likelihood | TruncatedNormal(lower 0), sigma HalfNormal(1) | KPI is non-negative. |

## Model structure

- Adstock: geometric, with `l_max` periods.
- Saturation: logistic.
- Seasonality: Fourier terms with `yearly_seasonality` harmonics.
- Channels are sorted alphabetically before priors are applied. The order matters for the spend-share prior.
