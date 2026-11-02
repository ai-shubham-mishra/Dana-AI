import re

PLAN_COMMAND_RE = re.compile(r"^/plans?(?=\s|$)\s*(.*)$", re.DOTALL | re.IGNORECASE)
PLAN_DIRECTIVE = (
    "The user invoked /plan. Follow the saved-plans flow in the plans skill: call list_plans, let the user pick a plan "
    "with ask_user, ask for the new model name, ask the training-window question as the plans skill requires, then "
    "call run_plan. Do not change the plan's stored configuration."
)


def expand_slash_command(text: str) -> str:
    """Turn a leading /plan or /plans into an instruction for the agent. Other text is returned unchanged."""
    match = PLAN_COMMAND_RE.match((text or "").strip())
    if match is None:
        return text
    rest = match.group(1).strip()
    return f"{PLAN_DIRECTIVE}\n\nUser message: {rest}" if rest else PLAN_DIRECTIVE
