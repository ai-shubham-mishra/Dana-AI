from langchain.agents.middleware import TodoListMiddleware


def build_middleware() -> list:
    return [TodoListMiddleware()]
