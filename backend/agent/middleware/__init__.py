from langchain.agents.middleware import TodoListMiddleware

from agent.middleware.hide_file_write_tools import HideFileWriteToolsMiddleware
from agent.middleware.todos import TODO_TOOL, todos_from_args


def build_middleware() -> list:
    return [TodoListMiddleware(), HideFileWriteToolsMiddleware()]


__all__ = ["HideFileWriteToolsMiddleware", "TODO_TOOL", "build_middleware", "todos_from_args"]
