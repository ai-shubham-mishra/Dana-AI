from typing import Any

from langgraph.types import interrupt

from integrations.plans.store import plan_slug

PLAN_DECISIONS = ["approve", "reject"]


def _first_decision(resume: Any) -> dict:
    decisions = resume.get("decisions") if isinstance(resume, dict) else None
    first = decisions[0] if decisions else None
    return first if isinstance(first, dict) else {}


def request_plan_approval(action: str, args: dict[str, Any], description: str) -> dict:
    # Raised from execute() so the approval card shows the saved configuration, not only the tool arguments.
    return _first_decision(
        interrupt(
            {
                "action_requests": [{"name": action, "args": args, "description": description}],
                "review_configs": [{"action_name": action, "allowed_decisions": PLAN_DECISIONS}],
            }
        )
    )


def describe_plan(doc: dict[str, Any], user_id: str) -> str:
    spec = doc.get("spec") or {}
    owner = "you" if doc.get("owner_id") == user_id else (doc.get("owner_email") or "a teammate")
    channels = ", ".join(spec.get("channels") or []) or "none"
    controls = ", ".join(spec.get("controls") or []) or "none"
    period = f"{spec.get('date_start', '?')} to {spec.get('date_end', '?')}"
    return "\n".join(
        [
            f"- {doc.get('name')} (slug /{plan_slug(doc)}, id {doc.get('id')}, {doc.get('visibility')}, owner {owner})",
            f"  KPI: {spec.get('kpi', '?')}",
            f"  Channels: {channels}",
            f"  Controls: {controls}",
            f"  Period: {period}",
        ]
    )
