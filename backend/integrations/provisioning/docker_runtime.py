"""Docker CLI adapter: builds the MMM API image and runs it locally with health polling."""

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from integrations.provisioning.models import BuiltImage, RunningContainer

Runner = Callable[..., subprocess.CompletedProcess]


class DockerError(RuntimeError):
    pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class DockerCli:
    def __init__(self, binary: str = "docker", runner: Runner = subprocess.run, http: httpx.Client | None = None) -> None:
        self._binary = binary
        self._runner = runner
        self._http = http or httpx.Client()

    def build(self, context_dir: Path, dockerfile: str, tag: str) -> BuiltImage:
        self._docker("build", "-f", str(context_dir / dockerfile), "-t", tag, str(context_dir))
        return BuiltImage(tag=tag)

    def run(self, image: BuiltImage, name: str, env: dict[str, str], container_port: int) -> RunningContainer:
        self._docker("rm", "-f", name, check=False)
        host_port = _free_port()
        args = ["run", "-d", "--name", name, "-p", f"127.0.0.1:{host_port}:{container_port}"]
        for key, value in env.items():
            args += ["-e", f"{key}={value}"]
        self._docker(*args, image.tag)
        return RunningContainer(name=name, image=image.tag, host_port=host_port, base_url=f"http://127.0.0.1:{host_port}")

    def wait_healthy(self, container: RunningContainer, timeout_s: float, interval_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        last = "no response yet"
        while time.monotonic() < deadline:
            status = self._docker("inspect", "-f", "{{.State.Status}}", container.name).strip()
            if status != "running":
                logs = self._docker("logs", "--tail", "60", container.name, check=False)
                raise DockerError(f"Container {container.name} is {status}. Last logs:\n{logs}")
            try:
                response = self._http.get(f"{container.base_url}/health", timeout=5.0)
                body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if response.status_code == 200 and body.get("model_loaded", True) is not False:
                    return body
                last = f"HTTP {response.status_code} {body}"
            except httpx.HTTPError as exc:
                last = str(exc)
            time.sleep(interval_s)
        raise DockerError(f"{container.name} not healthy after {timeout_s:.0f}s: {last}")

    def _docker(self, *args: str, check: bool = True) -> str:
        result = self._runner([self._binary, *args], capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise DockerError(f"docker {args[0]} failed: {(result.stderr or result.stdout).strip()[-2000:]}")
        return result.stdout
