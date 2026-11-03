TODO_TOOL = "write_todos"


def todos_from_args(args: dict) -> list[dict]:
    todos = args.get("todos")
    return todos if isinstance(todos, list) else []
