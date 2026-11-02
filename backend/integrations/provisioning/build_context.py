"""Builds a per-run Docker context from the MMM library, with the trained model baked in.

The library clone is never modified. Everything changed here lives in the per-run context directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from integrations.provisioning.models import ModelArtifact

DEMO_MODEL_REL = Path("mmm_library") / "demo_model.py"
DOCKERIGNORE_NAME = ".dockerignore"
MODEL_REL = Path("model") / "current_workspace_model.nc"
PATCH_ANCHOR = "            result = fetch_latest_model_from_workspace()\n"
PATCH_BLOCK = (
    '            if os.environ.get("MMM_MODEL_SOURCE") == "local":\n'
    '                raise RuntimeError("MMM_MODEL_SOURCE=local: using the local model file")\n'
)
_IGNORE_COPY = shutil.ignore_patterns(".git", ".venv", "venv_mmm_api", "__pycache__", "*.pyc")


class BuildContextError(RuntimeError):
    pass


def prepare_build_context(library_dir: Path, model: ModelArtifact, context_dir: Path) -> Path:
    if context_dir.exists():
        shutil.rmtree(context_dir)
    shutil.copytree(library_dir, context_dir, ignore=_IGNORE_COPY)
    _force_local_model(context_dir / DEMO_MODEL_REL)
    _allow_model_in_dockerignore(context_dir / DOCKERIGNORE_NAME)
    target = context_dir / MODEL_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(model.path, target)
    return context_dir


def _force_local_model(demo_model: Path) -> None:
    text = demo_model.read_text(encoding="utf-8")
    if text.count(PATCH_ANCHOR) != 1:
        raise BuildContextError(f"Patch anchor not found exactly once in {demo_model}")
    demo_model.write_text(text.replace(PATCH_ANCHOR, PATCH_BLOCK + PATCH_ANCHOR), encoding="utf-8")


def _allow_model_in_dockerignore(dockerignore: Path) -> None:
    lines = dockerignore.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if line.strip() != "/model/"]
    if len(kept) == len(lines):
        raise BuildContextError(f"'/model/' rule not found in {dockerignore}")
    dockerignore.write_text("".join(kept), encoding="utf-8")
