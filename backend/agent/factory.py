from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission
from langchain.agents.middleware import TodoListMiddleware
from langgraph.checkpoint.memory import MemorySaver

SYSTEM_PROMPT = (
    "You are Dana AI, an agent for marketing analytics and predictive modelling. "
    "Follow the rules in /AGENTS.md and the skills in /skills/."
)


def build_dana_agent(model, agent_root: Path, checkpointer=None):
    return create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        middleware=[TodoListMiddleware()],
        backend=FilesystemBackend(root_dir=agent_root, virtual_mode=True),
        memory=["/AGENTS.md"],
        skills=["/skills/"],
        permissions=[FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")],
        checkpointer=checkpointer or MemorySaver(),
        name="dana-ai",
    )
