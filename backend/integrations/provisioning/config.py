"""Provisioning settings. Every value can be overridden with a PROVISIONING_* environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_PREFIX = "PROVISIONING_"


@dataclass(frozen=True)
class ProvisioningConfig:
    repo_url: str = "https://github.com/EliyaHome/Analytics-Studio-Agentic-Backend.git"
    repo_branch: str = "staging"
    library_subdir: str = "mmm-library"
    workdir: Path = BACKEND_ROOT / "var" / "provisioning"
    training_root: Path = BACKEND_ROOT.parent / "var" / "training"
    image_repo: str = "dana-mmm-api"
    container_port: int = 5001
    port_range_start: int = 8100
    port_range_end: int = 8199
    health_timeout_s: float = 900.0
    health_interval_s: float = 3.0
    arm_base_url: str = "http://localhost:8080"
    subscription_id: str = "00000000-0000-0000-0000-000000000000"
    resource_group: str = "dana-ai-rg"
    location: str = "eastus"
    managed_environment_id: str = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/dana-ai-rg/providers/Microsoft.App/managedEnvironments/dana-ai-env"
    azure_token: str = field(default="mock-token", repr=False)
    github_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "ProvisioningConfig":
        env = os.environ if environ is None else environ
        overrides: dict[str, object] = {}
        for item in fields(cls):
            key = ENV_PREFIX + item.name.upper()
            if key not in env:
                continue
            raw = env[key]
            if item.name in {"workdir", "training_root"}:
                overrides[item.name] = Path(raw)
            elif item.name in {"container_port", "port_range_start", "port_range_end"}:
                overrides[item.name] = int(raw)
            elif item.name in {"health_timeout_s", "health_interval_s"}:
                overrides[item.name] = float(raw)
            else:
                overrides[item.name] = raw
        if "github_token" not in overrides and env.get("GITHUB_TOKEN"):
            overrides["github_token"] = env["GITHUB_TOKEN"]
        return cls(**overrides)
