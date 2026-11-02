---
name: plans
description: Use saved training plans. When the user types /plan or /plans, or asks to run, reuse, or list a plan, list the visible plans, let the user pick one, ask for the new model name, then run it. Also save a plan only when the user explicitly asks.
---

# Training plans

A plan is a saved, reusable training recipe. Running a plan always trains a brand-new model with the plan's exact stored configuration and date window. Plans never add versions to an existing model. Users create plans themselves on the Plans page, so never ask the user to create one in chat.

## /plan, /plans or "run a plan"

1. Call `list_plans`. Show the plans as a short list (name, KPI, channels, period, who owns it) only if the user did not already name one.
2. If the user has not picked a plan, ask which one with `ask_user`, offering the plan names as options.
3. Ask for the name of the new model with `ask_user` as a text question. Suggest a descriptive name. Do not reuse an existing model name.
4. Ask the training-window question with `ask_user`, defaulting to the plan's saved window.
5. Call `run_plan` with `plan_id` and `model_name`. The user sees the stored configuration on an approval card and approves or rejects it.
6. If `run_plan` reports that the name is taken, it lists unique suggestions. Ask the user to pick one, then call `run_plan` again.
7. After a successful run, tell the user the job is queued and that progress is on the Jobs tab.

Before calling `run_plan`, ask the training-window question as the `mmm-planning` skill does. Use the plan's saved window as the default. Do not change the stored configuration. If the user wants different settings, tell them to save a new plan or use the `mmm-planning` flow for a one-off run.

## Saving a plan from a conversation

Call `save_plan` only when the user explicitly asks to save the current training setup as a plan. Do not offer to save after each run. Pass the confirmed KPI, channels, controls, sources, date window, preparation, and overrides. Default visibility is `private`. Use `org` only when the user asks to share it with the organization, and tell them the creator is shown to everyone. The user approves the saved configuration before anything is stored.

If `save_plan` reports that the name is taken, ask the user for a different name and call it again.

## Rules

- Plans are strict. Do not change the stored parameters when running one.
- Always show the chosen plan name and the new model name before running.
- Only use `run_plan` for a plan returned by `list_plans` in this conversation or the user's explicit plan id.
