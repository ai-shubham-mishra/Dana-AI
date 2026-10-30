import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt

from agent import runtime
from agent.factory import build_dana_agent
from tests.fakes import ScriptedModel
from tests.test_api import make_settings

SUBAGENT_APPROVAL_SCRIPT = [
    AIMessage(
        content="",
        tool_calls=[{"name": "task", "args": {"description": "Train the MMM", "subagent_type": "general-purpose"}, "id": "parent-task"}],
    ),
    AIMessage(
        content="",
        tool_calls=[
            {
                "name": "start_training_job",
                "args": {"model": "mmm", "kpi": "sales", "channels": ["tv"], "date_range": "2024-01-01 to 2024-06-30"},
                "id": "sub-start",
            }
        ],
    ),
    AIMessage(content="Job queued."),
    AIMessage(content="All done."),
]


async def collect(agent, **kwargs):
    return [(event, data) for event, data in [item async for item in runtime.stream_turn(agent, "chat-chips", **kwargs)]]


def test_resumed_subagent_approval_emits_one_result_per_tool_call():
    settings = make_settings()
    agent = build_dana_agent(ScriptedModel(script=SUBAGENT_APPROVAL_SCRIPT), settings.agent_root, checkpointer=MemorySaver())

    first = asyncio.run(collect(agent, content="Train an MMM"))
    resumed = asyncio.run(collect(agent, decisions=[{"type": "approve"}]))

    paused_task = next(data["id"] for event, data in first if event == "tool_call" and data["name"] == "task")
    assert [event for event, _ in first][-1] == "interrupt"
    assert all(not (event == "tool_result" and data["id"] == paused_task) for event, data in first)

    results = [data for event, data in resumed if event == "tool_result"]
    starts = [data["id"] for event, data in resumed if event == "tool_call"]
    assert [result["id"] for result in results] == [
        starts[1],
        starts[0],
    ]
    assert all(not result.get("failed") for result in results)


def test_tool_error_is_reported_as_failed_and_graph_interrupt_is_ignored():
    events = [
        {"event": "on_tool_error", "name": "task", "run_id": "run-paused", "data": {"error": GraphInterrupt(())}},
        {"event": "on_tool_error", "name": "start_training_job", "run_id": "run-failed", "data": {"error": RuntimeError("boom")}},
    ]

    class FakeAgent:
        async def astream_events(self, payload, config, version):
            for event in events:
                yield event

        async def aget_state(self, config):
            return SimpleNamespace(values={}, interrupts=[])

    output = asyncio.run(collect(FakeAgent(), content="Train"))

    assert output == [("tool_result", {"id": "run-failed", "name": "start_training_job", "failed": True})]
