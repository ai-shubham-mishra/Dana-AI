"""Interfaces for each provisioning step, so the orchestrator can run against real tools or fakes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from integrations.provisioning.models import (
    BuiltImage,
    ModelArtifact,
    ProvisionedApp,
    RunningContainer,
    SourceCheckout,
)


class SourceCloner(Protocol):
    def checkout(self) -> SourceCheckout: ...


class ModelSource(Protocol):
    def resolve(self, run_id: str) -> ModelArtifact: ...


LogSink = Callable[[str], None]


class ImageBuilder(Protocol):
    def build(self, context_dir: Path, dockerfile: str, tag: str, log: LogSink | None = None) -> BuiltImage: ...


class ContainerRuntime(Protocol):
    def run(
        self,
        image: BuiltImage,
        name: str,
        env: dict[str, str],
        container_port: int,
        host_port: int | None = None,
    ) -> RunningContainer: ...

    def wait_healthy(
        self,
        container: RunningContainer,
        timeout_s: float,
        interval_s: float,
        log: LogSink | None = None,
    ) -> dict[str, Any]: ...

    def remove(self, name: str) -> None: ...


class CloudProvisioner(Protocol):
    def deploy(self, name: str, image: str, container_port: int, env: dict[str, str]) -> ProvisionedApp: ...
