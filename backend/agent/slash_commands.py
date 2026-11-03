import re
from datetime import date
from typing import Any

from integrations.plans.store import PLAN_NAME_MAX, SLUG_COMMANDS, PlanStore, plan_slug

SLASH_COMMAND_RE = re.compile(r"^/([a-z0-9][a-z0-9-]*)(?=\s|$)\s*(.*)$", re.DOTALL | re.IGNORECASE)
RUN_PLAN_RE = re.compile(r"^run the plan\s+/?([a-z0-9][a-z0-9-]*)(?=\s|$)\s*(.*)$", re.DOTALL | re.IGNORECASE)
PLANS_LIST_DIRECTIVE = (
    "The user invoked /plans. Call list_plans and show the saved plans, each with its slug as /<slug>, KPI, channels "
    "and period. Do not start a run; the user picks a plan next."
)


def plan_run_directive(plan: dict[str, Any]) -> str:
    name = str(plan.get("name") or "")[:PLAN_NAME_MAX]
    return (
        f"The user selected the saved plan '{name}' (slug /{plan_slug(plan)}, plan_id {plan.get('id')}). Skip listing "
        "and picking plans. Ask the user for the name of the new model, then call run_plan with plan_id and "
        f"model_name. The run keeps the plan's window length and ends today ({date.today().isoformat()}). "
        "Do not change the plan's stored configuration."
    )


async def expand_slash_command(text: str, plans: PlanStore | None, org_id: str, user_id: str) -> str:
    """Turn /plans, /<plan-slug> or 'run the plan <slug>' into an instruction for the agent. Other text is unchanged."""
    stripped = (text or "").strip()
    slash = SLASH_COMMAND_RE.match(stripped)
    match = slash or RUN_PLAN_RE.match(stripped)
    if match is None:
        return text
    command, rest = match.group(1).lower(), match.group(2).strip()
    if slash and command in SLUG_COMMANDS:
        directive = PLANS_LIST_DIRECTIVE
    else:
        if plans is None:
            return text
        plan = await plans.find_by_slug(org_id=org_id, user_id=user_id, slug=command)
        if plan is None:
            return text
        directive = plan_run_directive(plan)
    return f"{directive}\n\nUser message: {rest}" if rest else directive
