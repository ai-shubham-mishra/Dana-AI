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

## How to judge a run

- **Trusted:** divergences = 0 and `rhat_ok` = true. Report the channel contributions and the diminishing-returns picture.
- **Usable with caveats:** divergences small (under 1 percent of draws) or R-hat slightly above 1.1. Say the estimates are less certain and suggest more tuning or a longer window.
- **Not trusted:** many divergences or R-hat well above 1.1. Do not present channel contributions as facts. Propose one concrete fix (more tuning, a shorter adstock, dropping a collinear channel, or a longer window) and ask before rerunning.

## What to tell the user

- The window and row count, and which channels and controls were used.
- Any excluded channels and why.
- Whether the sampler converged, in one sentence.
- Where the model and run folder are, and that the Jobs tab shows the full history.

Do not claim ROI or budget recommendations beyond what the evaluation supports. Fit metrics beyond sampler health are not produced yet; say so if asked about accuracy.
