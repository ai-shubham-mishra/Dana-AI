from pydantic import Field

from agent.tools.base import PlannedTool, ToolInput


class CreateEvaluatorsInput(ToolInput):
    model: str = Field(description="Model family the evaluators are for, for example 'mmm'.")
    metrics: list[str] = Field(description="Metrics to evaluate, for example ['mape', 'r2'].")


class CreateEvaluatorsTool(PlannedTool):
    name: str = "create_evaluators"
    description: str = "Define the evaluation metrics and holdout checks used to score a trained model."
    planned_reason = "Evaluator creation is not connected yet, so no evaluators were defined."

    def get_input_schema(self) -> type[ToolInput]:
        return CreateEvaluatorsInput
