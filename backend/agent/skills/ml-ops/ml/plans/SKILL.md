---
name: plans
description: Use saved training plans. Each plan has a slug. When the user types /plans, lists plans, or asks to run or reuse one, call list_plans and show each plan as /<slug>. When the user types /<slug>, that plan is already chosen, so skip picking. Ask for the new model name, then run it. Save a plan only when the user explicitly asks.
---

# Training plans

A plan is a saved, reusable training recipe. Running a plan always trains a brand-new model with the plan's exact stored configuration. The date window keeps the plan's length but always ends on the run date (today), so every run uses the latest data. Plans never add versions to an existing model. Users create plans themselves on the Plans page, so never ask the user to create one in chat.

## /plans, or "run a plan"

1. Call `list_plans`. Show the plans as a short list (slug as /<slug>, name, KPI, channels, period, who owns it).
2. If the user has not picked a plan, ask which one with `ask_user`, offering the plan names as options.
3. Continue with the steps below.

## /<slug>

When the message starts with `/<slug>`, the directive already names the plan and its plan_id. Do not list or pick plans. Start at step 3.

## Running a chosen plan

1. Ask for the name of the new model with `ask_user` as a text question. Suggest a descriptive name. Do not reuse an existing model name.
2. Call `run_plan` with `plan_id` and `model_name`. The window keeps the plan's length and ends on today's date, so do not ask a window question. The user sees that configuration on an approval card and approves or rejects it.
3. If `run_plan` reports that the name is taken, it lists unique suggestions. Ask the user to pick one, then call `run_plan` again.
4. After a successful run, tell the user the job is queued and that progress is on the Jobs tab.


## Saving a plan from a conversation

Call `save_plan` only when the user explicitly asks to save the current training setup as a plan. Do not offer to save after each run. Pass the confirmed KPI, channels, controls, sources, date window, preparation, and overrides. Default visibility is `private`. Use `org` only when the user asks to share it with the organization, and tell them the creator is shown to everyone. The user approves the saved configuration before anything is stored.

If `save_plan` reports that the name is taken, ask the user for a different name and call it again.

## Rules

- Plans are strict. Do not change the stored parameters when running one.
- Always show the chosen plan name and the new model name before running.
- Only use `run_plan` for a plan returned by `list_plans` in this conversation, a plan named by a `/<slug>` directive, or the user's explicit plan id.
