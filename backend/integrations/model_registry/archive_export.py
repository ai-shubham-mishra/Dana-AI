import io
import json
import re
import zipfile
from collections.abc import Awaitable, Callable
from typing import Any

ReadModelFile = Callable[[str], Awaitable[tuple[str, bytes] | None]]


def archive_filename(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or "model"
    return f"{stem}.zip"


async def build_model_archive(*, model: dict[str, Any], read_model_file: ReadModelFile) -> bytes:
    entries: list[dict[str, Any]] = []
    files: list[tuple[str, bytes]] = []
    for version in model["versions"]:
        entry = {
            "version": version["version"],
            "job_id": version["job_id"],
            "source": version.get("source"),
            "kpi": version.get("kpi"),
            "tags": version.get("tags", []),
            "created_at": version.get("created_at"),
            "params": version.get("params"),
            "metrics": version.get("metrics"),
            "model_file": None,
        }
        stored = await read_model_file(version["job_id"])
        if stored is not None:
            file_name, data = stored
            path = f"v{version['version']}/{file_name}"
            entry["model_file"] = path
            files.append((path, data))
        entries.append(entry)

    manifest = {"model": {"id": model["id"], "name": model["name"]}, "versions": entries}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        for path, data in files:
            archive.writestr(path, data)
    return buffer.getvalue()
