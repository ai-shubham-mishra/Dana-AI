from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission
from langgraph.checkpoint.memory import MemorySaver

from agent.middleware import build_middleware

BASE_PROMPT = (
    "You are Dana AI, an agent for marketing analytics and predictive modelling. "
    "Follow the rules in /config/AGENTS.md and the skills in /skills/."
)


def load_system_prompt(agent_root: Path) -> str:
    parent_skill = (agent_root / "config" / "parent_skill.md").read_text(encoding="utf-8")
    return f"{BASE_PROMPT}\n\n{parent_skill}"


def build_dana_agent(model, agent_root: Path, checkpointer=None):
    return create_deep_agent(
        model=model,
        system_prompt=load_system_prompt(agent_root),
        middleware=build_middleware(),
        backend=FilesystemBackend(root_dir=agent_root, virtual_mode=True),
        memory=["/config/AGENTS.md"],
        skills=["/skills/"],
        permissions=[FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")],
        checkpointer=checkpointer or MemorySaver(),
        name="dana-ai",
    )
