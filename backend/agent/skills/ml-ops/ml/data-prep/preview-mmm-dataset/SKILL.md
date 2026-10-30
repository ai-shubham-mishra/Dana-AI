---
name: preview-mmm-dataset
description: Build the MMM dataset in memory and show its shape, dropped days, filled blanks and sample rows without saving or training. Use before start_mmm_run.
---

# preview_mmm_dataset

Use this after `profile_connector_columns` and before `start_mmm_run`. It takes the same fields as `start_mmm_run` (connector, KPI, channel spend, date window, `preparation`) and runs the real dataset build, then reports what the training run would receive. Nothing is saved and no job starts. It is read-only and needs no approval.

The output shows:

- Row count and date range.
- The columns, including the generated features.
- Days dropped because the KPI had no row.
- Blanks filled with 0, per output.
- History days read before the window for lags and rolling means.
- The first three and last two rows.

If the output is an error, the message names the fix (for example, a text metric that is not declared in `preparation.text_to_numeric`). Correct the plan and call it again.

Show the user the key numbers in plain language before you ask for approval to train.
