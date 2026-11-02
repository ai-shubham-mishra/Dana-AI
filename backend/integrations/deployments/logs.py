import asyncio
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

BACKLOG_BYTES = 256 * 1024
POLL_S = 0.5
_write_lock = threading.Lock()


def append_line(path: Path, line: str) -> None:
    with _write_lock, path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def _read_from(path: Path, offset: int) -> tuple[bytes, int]:
    size = path.stat().st_size
    if size < offset:
        offset = 0
    if size == offset:
        return b"", offset
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    return data, offset + len(data)


async def tail_lines(
    path: Path,
    is_active: Callable[[], Awaitable[bool]],
    *,
    poll_s: float = POLL_S,
    backlog_bytes: int = BACKLOG_BYTES,
) -> AsyncIterator[str]:
    """Yields the last lines of a log, then new lines as they are written, until the source is inactive."""
    path.touch(exist_ok=True)
    offset = max(0, path.stat().st_size - backlog_bytes)
    skip_partial = offset > 0
    pending = b""
    while True:
        active = await is_active()
        data, offset = await asyncio.to_thread(_read_from, path, offset)
        if data:
            *lines, pending = (pending + data).split(b"\n")
            for raw in lines:
                if skip_partial:
                    skip_partial = False
                    continue
                yield raw.decode("utf-8", "replace")
            continue
        if not active:
            if pending:
                yield pending.decode("utf-8", "replace")
            return
        await asyncio.sleep(poll_s)
