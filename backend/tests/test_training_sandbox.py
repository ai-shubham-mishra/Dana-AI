import asyncio

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.factory import build_dana_agent
from config.settings import get_settings
from integrations.llm.foundry import build_claude_model
from tests.fakes import ScriptedModel


class _Reader:
    def get_secret(self, name: str) -> str:
        return "https://foundry.example.test" if "ENDPOINT" in name else "test-key"


def test_agent_writes_run_artifacts_under_runs_and_denies_other_paths(tmp_path):
    script = [
        AIMessage(content="", tool_calls=[{"name": "write_file", "id": "w1", "args": {"file_path": "/runs/r1/train.py", "content": "print(1)"}}]),
        AIMessage(content="", tool_calls=[{"name": "write_file", "id": "w2", "args": {"file_path": "/config/evil.md", "content": "x"}}]),
        AIMessage(content="", tool_calls=[{"name": "read_file", "id": "r1", "args": {"file_path": "/runs/r1/train.py"}}]),
        AIMessage(content="done"),
    ]
    agent = build_dana_agent(
        ScriptedModel(script=script),
        get_settings().agent_root,
        checkpointer=MemorySaver(),
        runs_root=tmp_path,
    )
    result = asyncio.run(agent.ainvoke({"messages": [HumanMessage(content="train")]}, {"configurable": {"thread_id": "sandbox"}}))

    assert (tmp_path / "r1" / "train.py").read_text(encoding="utf-8") == "print(1)"
    assert not (get_settings().agent_root / "config" / "evil.md").exists()
    tool_results = {m.tool_call_id: m.content for m in result["messages"] if isinstance(m, ToolMessage)}
    assert "print(1)" in tool_results["r1"]
    assert "denied" in tool_results["w2"].lower() or "permission" in tool_results["w2"].lower()


def test_model_profile_defers_history_rewrites_to_near_context_limit():
    from deepagents.middleware.summarization import compute_summarization_defaults

    model = build_claude_model(_Reader(), "claude-sonnet-5-5")
    assert model.profile["max_input_tokens"] == 200_000
    defaults = compute_summarization_defaults(model)
    assert defaults["truncate_args_settings"]["trigger"] == ("fraction", 0.85)
    assert defaults["trigger"] == ("fraction", 0.85)
