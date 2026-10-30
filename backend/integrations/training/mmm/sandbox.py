"""Runs a generated training script in an isolated local subprocess.

The sandbox is a local stand-in for Azure ML: same inputs, same protocol, swappable later.
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from integrations.training.protocol import parse_line

SANDBOX_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
MAX_RUNTIME_S = 4 * 60 * 60
STDERR_TAIL = 20
# The final @@result line carries the full metrics payload on one line, which can exceed asyncio's 64 KiB default.
STREAM_LINE_LIMIT = 64 * 1024 * 1024

ProgressHandler = Callable[[dict[str, Any]], Awaitable[None]]


class SandboxError(RuntimeError):
    """Raised when the sandboxed script cannot run to completion."""


@dataclass(frozen=True)
class SandboxOutcome:
    code: int
    result: dict[str, Any] | None
    tail: list[str]


def sandbox_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    values = os.environ if source is None else source
    env = {key: values[key] for key in SANDBOX_ENV_KEYS if key in values}
    env["PYTHONUNBUFFERED"] = "1"
    return env


async def _drain(stream: asyncio.StreamReader, tail: deque[str]) -> None:
    async for raw in stream:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            tail.append(line)


async def run_script(
    argv: list[str],
    cwd: Path,
    on_progress: ProgressHandler,
    *,
    env: dict[str, str] | None = None,
    timeout_s: float = MAX_RUNTIME_S,
) -> SandboxOutcome:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=env if env is not None else sandbox_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=STREAM_LINE_LIMIT,
    )
    tail: deque[str] = deque(maxlen=STDERR_TAIL)
    drain = asyncio.create_task(_drain(proc.stderr, tail))
    result: dict[str, Any] | None = None
    try:
        async with asyncio.timeout(timeout_s):
            async for raw in proc.stdout:
                parsed = parse_line(raw.decode("utf-8", "replace").rstrip())
                if parsed is None:
                    continue
                kind, payload = parsed
                if kind == "progress":
                    await on_progress(payload)
                else:
                    result = payload
            code = await proc.wait()
            await drain
    except TimeoutError as exc:
        raise SandboxError(f"training exceeded {int(timeout_s)} seconds") from exc
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        drain.cancel()
    return SandboxOutcome(code=code, result=result, tail=list(tail))
