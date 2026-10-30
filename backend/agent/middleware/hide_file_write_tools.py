from langchain.agents.middleware import AgentMiddleware, ModelRequest

# Deepagents' summarization rewrites old write_file/edit_file arguments, which breaks signed thinking blocks.
HIDDEN_FILE_WRITE_TOOLS = frozenset({"write_file", "edit_file"})


def _tool_name(tool) -> str | None:
    return tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)


def visible_tools(tools) -> list:
    return [tool for tool in tools if _tool_name(tool) not in HIDDEN_FILE_WRITE_TOOLS]


class HideFileWriteToolsMiddleware(AgentMiddleware):
    """Removes file-write tools from the model request; the backend denies writes anyway."""

    def wrap_model_call(self, request: ModelRequest, handler):
        return handler(request.override(tools=visible_tools(request.tools)))

    async def awrap_model_call(self, request: ModelRequest, handler):
        return await handler(request.override(tools=visible_tools(request.tools)))
