import ast
import math
import operator

from pydantic import Field

from agent.tools.base import BaseTool, ToolInput, ToolOutput

MAX_EXPRESSION_LENGTH = 200
MAX_EXPONENT = 1000
MAX_RESULT_BITS = 4096

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
}


def _evaluate(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and _power_too_large(left, right):
            raise ValueError("The exponent is too large.")
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
        return _FUNCTIONS[node.func.id](*[_evaluate(arg) for arg in node.args])
    raise ValueError(f"Unsupported part of the expression: {type(node).__name__}.")


def _power_too_large(base, exponent) -> bool:
    if abs(exponent) > MAX_EXPONENT:
        return True
    return isinstance(base, int) and abs(base) > 1 and abs(exponent) * math.log2(abs(base)) > MAX_RESULT_BITS


def calculate(expression: str) -> float | int:
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"The expression is longer than {MAX_EXPRESSION_LENGTH} characters.")
    tree = ast.parse(expression.strip(), mode="eval")
    value = _evaluate(tree)
    if isinstance(value, complex):
        raise ValueError("The result is not a real number.")
    return value


class CalculateInput(ToolInput):
    expression: str = Field(
        description=(
            "Arithmetic expression such as '(1250000 - 980000) / 980000 * 100'. Supports + - * / // % **, parentheses, "
            "and sqrt, log, log10, exp, abs, round, min, max, floor, ceil, pi, e, tau."
        )
    )


class CalculateTool(BaseTool):
    name: str = "calculate"
    description: str = (
        "Evaluate an arithmetic expression exactly. Use it for every calculation such as totals, percentages, "
        "growth rates and ratios instead of doing the math in your head."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return CalculateInput

    async def execute(self, expression: str) -> ToolOutput:
        try:
            value = calculate(expression)
        except SyntaxError:
            return ToolOutput(success=False, error=f"'{expression}' is not a valid arithmetic expression.")
        except (ArithmeticError, ValueError, TypeError) as exc:
            return ToolOutput(success=False, error=f"Cannot calculate '{expression}': {exc}")
        text = f"{value:.10g}" if isinstance(value, float) else str(value)
        return ToolOutput(result=f"{expression.strip()} = {text}", metadata={"value": text})
