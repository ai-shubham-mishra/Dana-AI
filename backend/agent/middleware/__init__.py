from langchain.agents.middleware import TodoListMiddleware

from agent.middleware.todos import TODO_TOOL, todos_from_args


def build_middleware() -> list:
    return [TodoListMiddleware()]


__all__ = ["TODO_TOOL", "build_middleware", "todos_from_args"]
