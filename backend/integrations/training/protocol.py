import json
from typing import Any

PROGRESS_PREFIX = "@@progress "
RESULT_PREFIX = "@@result "


def emit(prefix: str, payload: dict[str, Any]) -> None:
    print(prefix + json.dumps(payload, default=str), flush=True)


def parse_line(line: str) -> tuple[str, dict[str, Any]] | None:
    for kind, prefix in (("progress", PROGRESS_PREFIX), ("result", RESULT_PREFIX)):
        if line.startswith(prefix):
            try:
                payload = json.loads(line[len(prefix):])
            except json.JSONDecodeError:
                return None
            return (kind, payload) if isinstance(payload, dict) else None
    return None
