"""Immutable records passed between provisioning steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceCheckout:
    repo_url: str
    branch: str
    sha: str
    library_dir: Path


@dataclass(frozen=True)
class ModelArtifact:
    run_id: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class BuiltImage:
    tag: str


@dataclass(frozen=True)
class RunningContainer:
    name: str
    image: str
    host_port: int
    base_url: str


@dataclass(frozen=True)
class ProvisionedApp:
    name: str
    fqdn: str | None
    provisioning_state: str | None


@dataclass(frozen=True)
class ProvisionResult:
    run_id: str
    source_sha: str
    image: BuiltImage
    container: RunningContainer
    health: dict[str, Any]
    app: ProvisionedApp | None = None
    warnings: list[str] = field(default_factory=list)
