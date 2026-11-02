"""Docker CLI adapter: builds the MMM API image and runs it locally with health polling."""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from integrations.provisioning.models import BuiltImage, RunningContainer
from integrations.provisioning.ports import LogSink

Runner = Callable[..., subprocess.CompletedProcess]


class DockerError(RuntimeError):
    pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LogFollower:
    """Streams `docker logs -f` into a sink on a daemon thread until stop() is called."""

    def __init__(self, process: subprocess.Popen, sink: LogSink) -> None:
        self._process = process
        self._thread = threading.Thread(target=self._pump, args=(sink,), daemon=True)
        self._thread.start()

    def _pump(self, sink: LogSink) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            sink(line.rstrip("\n"))

    def stop(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._thread.join(timeout=5)


class DockerCli:
    def __init__(self, binary: str = "docker", runner: Runner = subprocess.run, http: httpx.Client | None = None) -> None:
        self._binary = binary
        self._runner = runner
        self._http = http or httpx.Client()

    def build(self, context_dir: Path, dockerfile: str, tag: str, log: LogSink | None = None) -> BuiltImage:
        self._docker("build", "-f", str(context_dir / dockerfile), "-t", tag, str(context_dir), log=log)
        return BuiltImage(tag=tag)

    def run(
        self,
        image: BuiltImage,
        name: str,
        env: dict[str, str],
        container_port: int,
        host_port: int | None = None,
    ) -> RunningContainer:
        self._docker("rm", "-f", name, check=False)
        host_port = host_port or _free_port()
        args = ["run", "-d", "--name", name, "-p", f"127.0.0.1:{host_port}:{container_port}"]
        for key, value in env.items():
            args += ["-e", f"{key}={value}"]
        self._docker(*args, image.tag)
        return RunningContainer(name=name, image=image.tag, host_port=host_port, base_url=f"http://127.0.0.1:{host_port}")

    def wait_healthy(
        self,
        container: RunningContainer,
        timeout_s: float,
        interval_s: float,
        log: LogSink | None = None,
    ) -> dict[str, Any]:
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
                    if log:
                        log("Health check passed: model loaded")
                    return body
                current = f"HTTP {response.status_code} {body}"
            except httpx.HTTPError as exc:
                current = str(exc)
            if log and current != last:
                log(f"Waiting for health check: {current}")
            last = current
            time.sleep(interval_s)
        raise DockerError(f"{container.name} not healthy after {timeout_s:.0f}s: {last}")

    def remove(self, name: str) -> None:
        self._docker("rm", "-f", name, check=False)

    def follow_logs(self, name: str, sink: LogSink) -> LogFollower:
        process = subprocess.Popen(
            [self._binary, "logs", "-f", "--tail", "100", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        return LogFollower(process, sink)

    def _docker(self, *args: str, check: bool = True, log: LogSink | None = None) -> str:
        if log is not None:
            return self._stream(args, check, log)
        result = self._runner([self._binary, *args], capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise DockerError(f"docker {args[0]} failed: {(result.stderr or result.stdout).strip()[-2000:]}")
        return result.stdout

    def _stream(self, args: tuple[str, ...], check: bool, log: LogSink) -> str:
        process = subprocess.Popen(
            [self._binary, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip("\n")
            lines.append(text)
            log(text)
        process.wait()
        output = "\n".join(lines)
        if check and process.returncode != 0:
            raise DockerError(f"docker {args[0]} failed: {output.strip()[-2000:]}")
        return output + "\n"

