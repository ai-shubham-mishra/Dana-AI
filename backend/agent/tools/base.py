import logging
from abc import abstractmethod
from typing import Any, ClassVar

from langchain_core.tools import BaseTool as LangChainBaseTool
from langgraph.errors import GraphBubbleUp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolInput(BaseModel):
    """Base class for tool inputs."""


class ToolOutput(BaseModel):
    success: bool = True
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTool(LangChainBaseTool):
    """Blueprint for every agent tool. Subclasses set name, description, the input schema and execute()."""

    name: str = ""
    description: str = ""
    # Decisions a human may take before this tool runs. None means the tool runs without approval.
    allowed_decisions: ClassVar[list[str] | None] = None

    @abstractmethod
    def get_input_schema(self) -> type[ToolInput]:
        """Return the Pydantic model that validates this tool's arguments."""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolOutput:
        """Run the tool and return structured output."""

    def _run(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError(f"{self.name} runs async only; invoke it with ainvoke.")

    async def _arun(self, **kwargs: Any) -> str:
        try:
            output = await self.execute(**kwargs)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            logger.exception("tool %s failed", self.name)
            return f"Error: {exc}"
        if not output.success:
            return f"Error: {output.error}"
        return str(output.result)


class PlannedTool(BaseTool):
    """A tool whose backend is not connected yet. It tells the agent so instead of pretending to work."""

    planned_reason: ClassVar[str] = "This capability is not connected yet."

    async def execute(self, **kwargs: Any) -> ToolOutput:
        return ToolOutput(success=False, error=self.planned_reason)
