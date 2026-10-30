---
name: run-script
description: How the MMM training script is generated on the fly from a template for each run, which placeholders it fills, and what the generated script must emit so the platform can track progress.
---

# MMM run script

The training script is not a fixed file. For every run, the platform renders [train_template.py.tmpl](./train_template.py.tmpl) with the approved configuration and writes the result as `train.py` into the run folder. The agent does not write this code by hand.

## Placeholders

The template contains three placeholders. Each is replaced with a Python literal (`repr`), so values are never executed as code.

| Placeholder | Filled with |
|---|---|
| `{{CONFIG_LITERAL}}` | The full resolved configuration (the same content as `config.yml`). |
| `{{PLAN_SUMMARY_LITERAL}}` | One-line summary of the plan, for the script header and the job log. |
| `{{GENERATED_AT_LITERAL}}` | ISO timestamp of generation. |

Rendering fails if any `{{...}}` token is left over, so the template and the renderer must stay in sync.

## What the generated script must do

1. Read `dataset.csv` from its own folder (never from an absolute path).
2. Drop channels with less than the minimum total spend and record them.
3. Build the MMM with the priors from the configuration, deriving the spend-share sigma for `saturation_beta`.
4. Sample, then check divergences and R-hat.
5. Sample posterior predictive only when there are no divergences.
6. Save `mmm_model.nc` into its own folder.
7. Write `evaluation.json` into its own folder.

## Protocol

The platform reads stdout line by line:

- `@@progress {"stage": ..., "percent": 0-100, "message": ...}` for each milestone.
- `@@result {"status": "success", "model_path": "mmm_model.nc", "metrics": {...}}` on success.
- `@@result {"status": "error", "message": ...}` on failure, then exit with a non-zero code.

Any other stdout or stderr text is kept as the job log tail.

## Constraints

- Only the libraries already in the backend environment: numpy, pandas, arviz, pymc, pymc_extras, pymc_marketing.
- No network calls, no reading of environment secrets, no writes outside the run folder.
- Keep the template generic. Client-specific choices come from the configuration, not from edits to the template.
