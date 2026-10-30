import asyncio
from dataclasses import dataclass, field

from agent.middleware import build_middleware
from agent.middleware.hide_file_write_tools import HideFileWriteToolsMiddleware, visible_tools


@dataclass
class _Tool:
    name: str


@dataclass
class _Request:
    tools: list = field(default_factory=list)

    def override(self, **changes):
        return _Request(**{**self.__dict__, **changes})


def _names(tools):
    return [t.name if not isinstance(t, dict) else t["name"] for t in tools]


def test_write_and_edit_file_are_hidden_from_model_tools():
    tools = [_Tool("ls"), _Tool("write_file"), {"name": "edit_file"}, _Tool("write_todos")]
    assert _names(visible_tools(tools)) == ["ls", "write_todos"]


def test_wrap_model_call_forwards_request_without_file_write_tools():
    seen = []

    def handler(request):
        seen.append(_names(request.tools))
        return "ok"

    request = _Request(tools=[_Tool("query_database"), _Tool("write_file")])
    assert HideFileWriteToolsMiddleware().wrap_model_call(request, handler) == "ok"
    assert seen == [["query_database"]]


def test_awrap_model_call_forwards_request_without_file_write_tools():
    seen = []

    async def handler(request):
        seen.append(_names(request.tools))
        return "ok"

    request = _Request(tools=[_Tool("edit_file"), _Tool("list_channels")])
    assert asyncio.run(HideFileWriteToolsMiddleware().awrap_model_call(request, handler)) == "ok"
    assert seen == [["list_channels"]]


def test_middleware_is_registered_for_the_agent():
    assert any(isinstance(m, HideFileWriteToolsMiddleware) for m in build_middleware())
