---
name: mmm-planning
description: Plan and start a Marketing Mix Model training run - collect the inputs, map them to the bundled dataset, then request training for approval.
---

# MMM planning and training

Use this skill when the user wants to build, run, or understand a Marketing Mix Model.

## Steps

1. Confirm the business KPI (for example revenue, conversions, or sign-ups) and its currency.
2. Ask which marketing channels to model (for example Meta Ads, Google Ads, TV, email).
3. Ask for the date range of the historical data, in the form `YYYY-MM-DD to YYYY-MM-DD`.
4. Ask which connector or data source holds each channel's spend and the KPI.
5. Summarize the inputs in a short list and confirm them before proposing next steps.
6. When the user asks to train, call `start_training_job` with `model="mmm"`, the KPI, the channels, and the date range. A human approves, edits, or rejects the request first.

## Bundled dataset (for now)

Training runs only on the bundled sample dataset until client connectors are available.

- KPI: `sales`
- Channels: `Google-Demand-Gen`, `Google-PMax`, `Google-Search`, `YouTube`, `Meta-ASC`, `Meta-Reach`, `Meta-Performance`, `TV`, `Microsoft`, `Pinterest`
- Data starts on 2023-04-24 (weekly rows).

If the user asks for a KPI or channel outside this list, say so and do not submit the request. Ask the user to choose from the list, or wait for connectors.

## Boundaries

- Do not claim any results before a job has succeeded. Point the user to the Jobs tab for progress and output.
- Do not guess column names or values. Ask the user.
- Do not submit a training request until the KPI, channels, and date range are confirmed.
