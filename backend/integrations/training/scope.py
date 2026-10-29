from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobScope:
    service: Any
    org_id: str
    user_id: str
    chat_id: str


_scope: ContextVar[JobScope | None] = ContextVar("training_job_scope", default=None)


def bind_scope(scope: JobScope | None) -> None:
    _scope.set(scope)


def current_scope() -> JobScope | None:
    return _scope.get()
