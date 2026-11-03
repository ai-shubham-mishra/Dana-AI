from agent.tools.base import BaseTool, ToolInput, ToolOutput
from agent.tools.ml_ops.ml.plans.common import describe_plan
from integrations.training.scope import current_scope

LIST_PLANS_TOOL = "list_plans"


class ListPlansTool(BaseTool):
    name: str = LIST_PLANS_TOOL
    description: str = (
        "List the saved training plans the user can see: their own plans plus plans shared with the organization. "
        "Each plan is a reusable recipe. Call this first for /plans or when the user asks to use a plan, then run one "
        "with run_plan. Users create plans on the Plans page; never ask the user to create a plan in chat."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return ToolInput

    async def execute(self, **kwargs) -> ToolOutput:
        scope = current_scope()
        if scope is None or scope.plans is None:
            return ToolOutput(success=False, error="Plans are unavailable in this context.")
        plans = await scope.plans.list_visible(org_id=scope.org_id, user_id=scope.user_id)
        if not plans:
            return ToolOutput(
                result="The user has no saved plans yet. Do not ask them to create one; they create plans on the Plans page."
            )
        return ToolOutput(result="\n".join(describe_plan(plan, scope.user_id) for plan in plans))
