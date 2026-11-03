"""Draft training scripts: where they live on disk and how the agent may change them."""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

RUN_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_SCRIPT_CHARS = 60_000
DRAFT_META_FILE = "draft.json"


class DraftError(ValueError):
    """The draft cannot be used as requested. The message is safe to show the agent and the user."""


def draft_dir(root: Path, org_id: str, user_id: str, chat_id: str, run_id: str) -> Path:
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise DraftError(f"{run_id!r} is not a valid run_id. Use the run_id returned by create_training_script.")
    scope = hashlib.sha256("\x1f".join((org_id, user_id, chat_id)).encode("utf-8")).hexdigest()[:32]
    return root / "drafts" / scope / run_id


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def apply_script_edit(script: str, old_text: str, new_text: str) -> str:
    if not old_text:
        raise DraftError("old_text must not be empty. Copy the exact text to replace from the script.")
    matches = script.count(old_text)
    if matches == 0:
        raise DraftError("old_text was not found in the script. Copy it exactly, including indentation.")
    if matches > 1:
        raise DraftError(
            f"old_text appears {matches} times in the script. Include more surrounding lines so it matches once."
        )
    updated = script.replace(old_text, new_text, 1)
    if len(updated) > MAX_SCRIPT_CHARS:
        raise DraftError(f"the script would be {len(updated)} characters, over the {MAX_SCRIPT_CHARS} limit.")
    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise DraftError(f"the edit leaves the script invalid Python at line {exc.lineno}: {exc.msg}.") from exc
    return updated
