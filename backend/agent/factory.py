from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission
from langgraph.checkpoint.memory import MemorySaver

from agent.middleware import build_middleware
from agent.tools.registry import build_tools, interrupt_policy

BASE_PROMPT = (
    "You are Dana AI, an agent for marketing analytics and predictive modelling. "
    "Follow the rules in /config/AGENTS.md and the skills in /skills/. "
    "Write each run's training script, config.yml and dataset.csv under /runs/<run_id>/. "
    "Every other path is read-only."
)
RUNS_ROUTE = "/runs/"


def load_system_prompt(agent_root: Path) -> str:
    parent_skill = (agent_root / "config" / "parent_skill.md").read_text(encoding="utf-8")
    return f"{BASE_PROMPT}\n\n{parent_skill}"


def skill_sources(agent_root: Path) -> list[str]:
    """One skill source per folder that directly holds skill folders, so the nested skills tree is discovered."""
    sources = {"/skills/"}
    for skill_file in (agent_root / "skills").rglob("SKILL.md"):
        sources.add("/" + skill_file.parent.parent.relative_to(agent_root).as_posix() + "/")
    return sorted(sources)


def build_dana_agent(
    model,
    agent_root: Path,
    checkpointer=None,
    connector_pool=None,
    datasets_schema: str = "datasets",
    runs_root: Path | None = None,
):
    runs_root = runs_root or agent_root.parent / "training" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    tools = build_tools(connector_pool=connector_pool, datasets_schema=datasets_schema)
    return create_deep_agent(
        model=model,
        system_prompt=load_system_prompt(agent_root),
        middleware=build_middleware(),
        tools=tools,
        interrupt_on=interrupt_policy(tools),
        backend=CompositeBackend(
            default=FilesystemBackend(root_dir=agent_root, virtual_mode=True),
            routes={RUNS_ROUTE: FilesystemBackend(root_dir=runs_root, virtual_mode=True)},
        ),
        memory=["/config/AGENTS.md"],
        skills=skill_sources(agent_root),
        permissions=[
            FilesystemPermission(operations=["read", "write"], paths=[f"{RUNS_ROUTE}**"], mode="allow"),
            FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        ],
        checkpointer=checkpointer or MemorySaver(),
        name="dana-ai",
    )
