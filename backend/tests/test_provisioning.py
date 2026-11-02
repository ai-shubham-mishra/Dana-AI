import json
import subprocess
from pathlib import Path

import httpx
import pytest

from integrations.provisioning.arm_client import ArmError, ContainerAppsClient
from integrations.provisioning.build_context import BuildContextError, prepare_build_context
from integrations.provisioning.config import ProvisioningConfig
from integrations.provisioning.docker_runtime import DockerCli, DockerError
from integrations.provisioning.git_source import GitSourceCloner, GitSourceError
from integrations.provisioning.model_source import LocalTrainingModelSource, ModelNotFoundError
from integrations.provisioning.models import BuiltImage, ModelArtifact, ProvisionedApp, RunningContainer
from integrations.provisioning.orchestrator import ProvisioningOrchestrator

DEMO_MODEL = (
    "import os\n"
    "\n"
    "def fetch_latest_model_from_workspace():\n"
    "    return {}\n"
    "\n"
    "def init():\n"
    "    try:\n"
    "        try:\n"
    "            logger.info('Fetching')\n"
    "            result = fetch_latest_model_from_workspace()\n"
    "            return result\n"
    "        except Exception as e:\n"
    "            pass\n"
)


def _library(root: Path) -> Path:
    lib = root / "mmm-library"
    (lib / "mmm_library").mkdir(parents=True)
    (lib / "mmm_library" / "demo_model.py").write_text(DEMO_MODEL, encoding="utf-8")
    (lib / "Dockerfile.api").write_text("FROM python:3.12.4-slim\n", encoding="utf-8")
    (lib / ".dockerignore").write_text(".git/\n/model/\n/data/\n", encoding="utf-8")
    (lib / ".git").mkdir()
    (lib / ".git" / "HEAD").write_text("x", encoding="utf-8")
    return lib


def _model(root: Path, run_id: str = "run-1", payload: bytes = b"NETCDF") -> ModelArtifact:
    path = root / run_id / "mmm_model.nc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return ModelArtifact(run_id=run_id, path=path, size_bytes=len(payload))


def _completed(stdout: str = "", stderr: str = "", code: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


# --- config -----------------------------------------------------------------

def test_config_defaults_and_env_overrides(tmp_path):
    cfg = ProvisioningConfig.from_env({
        "PROVISIONING_REPO_BRANCH": "feature/x",
        "PROVISIONING_CONTAINER_PORT": "6001",
        "PROVISIONING_WORKDIR": str(tmp_path),
        "GITHUB_TOKEN": "ghp_test",
    })
    assert cfg.repo_branch == "feature/x"
    assert cfg.container_port == 6001
    assert cfg.workdir == tmp_path
    assert cfg.github_token == "ghp_test"
    assert cfg.repo_url.endswith("Analytics-Studio-Agentic-Backend.git")
    assert "ghp_test" not in repr(cfg)


# --- model source -----------------------------------------------------------

def test_default_workdir_is_repo_var_outside_reload_watched_tree():
    from config.settings import BACKEND_ROOT

    default = ProvisioningConfig().workdir
    assert default == BACKEND_ROOT.parent / "var" / "provisioning"
    assert not default.is_relative_to(BACKEND_ROOT)


def test_model_source_resolves_run_model(tmp_path):
    _model(tmp_path, "abc")
    artifact = LocalTrainingModelSource(tmp_path).resolve("abc")
    assert artifact.path == tmp_path / "abc" / "mmm_model.nc"
    assert artifact.size_bytes == len(b"NETCDF")


def test_model_source_missing_and_empty(tmp_path):
    with pytest.raises(ModelNotFoundError):
        LocalTrainingModelSource(tmp_path).resolve("nope")
    _model(tmp_path, "empty", payload=b"")
    with pytest.raises(ModelNotFoundError):
        LocalTrainingModelSource(tmp_path).resolve("empty")


def test_model_source_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        LocalTrainingModelSource(tmp_path).resolve("../etc")


# --- git source -------------------------------------------------------------

def test_git_clone_is_shallow_sparse_and_returns_sha(tmp_path):
    calls = []
    dest = tmp_path / "source"

    def runner(argv, **kwargs):
        calls.append(argv)
        if argv[-2:] == ["rev-parse", "HEAD"] or "rev-parse" in argv:
            return _completed(stdout="52a19501eb4b9c234f0841642a5ba97c42fd98d0\n")
        if "clone" in argv:
            _library(dest)
        return _completed()

    cloner = GitSourceCloner("https://github.com/o/r.git", "staging", "mmm-library", dest, runner=runner)
    checkout = cloner.checkout()
    clone = next(c for c in calls if "clone" in c)
    assert "--branch" in clone and clone[clone.index("--branch") + 1] == "staging"
    assert "--depth" in clone and "--sparse" in clone
    assert checkout.sha == "52a19501eb4b9c234f0841642a5ba97c42fd98d0"
    assert checkout.library_dir == dest / "mmm-library"


def test_git_token_is_passed_per_call_and_redacted_from_errors(tmp_path):
    token = "ghp_secret123"

    def runner(argv, **kwargs):
        return _completed(stderr=f"fatal: could not read {token}", code=128)

    cloner = GitSourceCloner("https://github.com/o/r.git", "staging", "mmm-library", tmp_path / "s", token=token, runner=runner)
    with pytest.raises(GitSourceError) as err:
        cloner.checkout()
    assert token not in str(err.value)
    assert "***" in str(err.value)


# --- build context ----------------------------------------------------------

def test_build_context_patches_demo_model_and_bakes_model(tmp_path):
    lib = _library(tmp_path / "src")
    model = _model(tmp_path / "runs")
    ctx = prepare_build_context(lib, model, tmp_path / "ctx")

    patched = (ctx / "mmm_library" / "demo_model.py").read_text(encoding="utf-8")
    guard = patched.index('MMM_MODEL_SOURCE") == "local"')
    assert guard < patched.index("result = fetch_latest_model_from_workspace()")
    assert (ctx / "model" / "current_workspace_model.nc").read_bytes() == b"NETCDF"
    assert "/model/" not in (ctx / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "/data/" in (ctx / ".dockerignore").read_text(encoding="utf-8")
    assert not (ctx / ".git").exists()
    # The source clone must stay untouched.
    assert (lib / "mmm_library" / "demo_model.py").read_text(encoding="utf-8") == DEMO_MODEL


def test_build_context_fails_when_anchor_missing(tmp_path):
    lib = _library(tmp_path / "src")
    (lib / "mmm_library" / "demo_model.py").write_text("print('changed upstream')\n", encoding="utf-8")
    with pytest.raises(BuildContextError):
        prepare_build_context(lib, _model(tmp_path / "runs"), tmp_path / "ctx")


# --- docker runtime ---------------------------------------------------------

def test_docker_wait_healthy_polls_until_model_loaded():
    responses = [httpx.Response(503, json={"model_loaded": False}), httpx.Response(200, json={"model_loaded": True, "status": "loaded"})]
    http = httpx.Client(transport=httpx.MockTransport(lambda request: responses.pop(0)))

    def runner(argv, **kwargs):
        return _completed(stdout="running\n")

    docker = DockerCli(runner=runner, http=http)
    container = RunningContainer(name="c", image="img", host_port=1, base_url="http://127.0.0.1:1")
    body = docker.wait_healthy(container, timeout_s=5, interval_s=0)
    assert body["model_loaded"] is True


def test_docker_wait_healthy_fails_fast_when_container_exits():
    def runner(argv, **kwargs):
        if "inspect" in argv:
            return _completed(stdout="exited\n")
        return _completed(stdout="ValueError: bad model\n")

    docker = DockerCli(runner=runner, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    container = RunningContainer(name="c", image="img", host_port=1, base_url="http://127.0.0.1:1")
    with pytest.raises(DockerError, match="bad model"):
        docker.wait_healthy(container, timeout_s=5, interval_s=0)


def test_docker_run_publishes_localhost_port_and_env():
    seen = []

    def runner(argv, **kwargs):
        seen.append(argv)
        return _completed()

    container = DockerCli(runner=runner).run(BuiltImage("dana-mmm-api:x"), "dana-mmm-x", {"MMM_MODEL_SOURCE": "local"}, 5001)
    run_argv = next(a for a in seen if "run" in a)
    assert "127.0.0.1:%d:5001" % container.host_port in run_argv
    assert "MMM_MODEL_SOURCE=local" in run_argv
    assert run_argv[-1] == "dana-mmm-api:x"


# --- ARM client -------------------------------------------------------------

def _arm(handler) -> ContainerAppsClient:
    return ContainerAppsClient(
        base_url="http://arm.test",
        subscription_id="sub",
        resource_group="rg",
        location="eastus",
        managed_environment_id="/env",
        token="t",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        poll_interval_s=0,
        timeout_s=5,
    )


def test_arm_deploy_polls_async_operation_then_reads_fqdn():
    polls = iter(["InProgress", "Succeeded"])
    state = {"puts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            state["puts"] += 1
            body = json.loads(request.content)
            assert body["properties"]["template"]["containers"][0]["image"] == "dana-mmm-api:x"
            assert request.headers["Authorization"] == "Bearer t"
            return httpx.Response(201, headers={"Azure-AsyncOperation": "http://arm.test/op"}, json={})
        if request.url.path == "/op":
            return httpx.Response(200, json={"status": next(polls)})
        return httpx.Response(200, json={"properties": {"provisioningState": "Succeeded", "configuration": {"ingress": {"fqdn": "app.test"}}}})

    app = _arm(handler).deploy("mmm-x", "dana-mmm-api:x", 5001, {"MMM_MODEL_SOURCE": "local"})
    assert app == ProvisionedApp(name="mmm-x", fqdn="app.test", provisioning_state="Succeeded")
    assert state["puts"] == 1


def test_arm_deploy_raises_on_failed_operation():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(201, headers={"Azure-AsyncOperation": "http://arm.test/op"}, json={})
        return httpx.Response(200, json={"status": "Failed", "error": {"code": "Boom"}})

    with pytest.raises(ArmError, match="Failed"):
        _arm(handler).deploy("mmm-x", "img", 5001, {})


# --- orchestrator -----------------------------------------------------------

class _Recorder:
    def __init__(self):
        self.steps = []

    def record(self, name):
        self.steps.append(name)


class _Cloner:
    def __init__(self, rec, lib):
        self.rec, self.lib = rec, lib

    def checkout(self):
        self.rec.record("clone")
        from integrations.provisioning.models import SourceCheckout
        return SourceCheckout("repo", "staging", "sha123", self.lib)


class _ModelSource:
    def __init__(self, rec, model):
        self.rec, self.model = rec, model

    def resolve(self, run_id):
        self.rec.record("model")
        return self.model


class _Builder:
    def __init__(self, rec):
        self.rec = rec

    def build(self, context_dir, dockerfile, tag, log=None):
        self.rec.record("build")
        assert dockerfile == "Dockerfile.api"
        assert (context_dir / "model" / "current_workspace_model.nc").is_file()
        if log:
            log("built")
        return BuiltImage(tag)


class _Runtime:
    def __init__(self, rec):
        self.rec = rec
        self.runs = []
        self.removed = []

    def run(self, image, name, env, container_port, host_port=None):
        self.rec.record("run")
        assert env == {"MMM_MODEL_SOURCE": "local"}
        self.runs.append((name, host_port))
        return RunningContainer(name, image.tag, host_port or 9999, f"http://127.0.0.1:{host_port or 9999}")

    def wait_healthy(self, container, timeout_s, interval_s, log=None):
        self.rec.record("health")
        return {"status": "loaded", "model_loaded": True}

    def remove(self, name):
        self.removed.append(name)


class _Cloud:
    def __init__(self, rec):
        self.rec = rec
        self.calls = []

    def deploy(self, name, image, container_port, env):
        self.rec.record("cloud")
        self.calls.append((name, image))
        return ProvisionedApp(name, "mock.test", "Succeeded")


def _orchestrator(tmp_path, rec, cloud):
    cfg = ProvisioningConfig(workdir=tmp_path / "wd")
    return ProvisioningOrchestrator(
        cfg,
        _Cloner(rec, _library(tmp_path / "src")),
        _ModelSource(rec, _model(tmp_path / "runs", "Run_1")),
        _Builder(rec),
        _Runtime(rec),
        cloud,
    )


def test_orchestrator_runs_full_flow_in_order(tmp_path):
    rec = _Recorder()
    cloud = _Cloud(rec)
    result = _orchestrator(tmp_path, rec, cloud).provision("Run_1")
    assert rec.steps == ["model", "clone", "build", "run", "health", "cloud"]
    assert result.source_sha == "sha123"
    assert result.app.fqdn == "mock.test"
    assert result.image.tag == "dana-mmm-api:run_1"
    assert cloud.calls[0][0].startswith("mmm-")
    assert result.warnings and "registry" in result.warnings[0]


def test_orchestrator_no_cloud_skips_arm(tmp_path):
    rec = _Recorder()
    cloud = _Cloud(rec)
    result = _orchestrator(tmp_path, rec, cloud).provision("Run_1", deploy_cloud=False)
    assert "cloud" not in rec.steps
    assert result.app is None
    assert result.warnings == []


def test_orchestrator_instance_id_host_port_and_log(tmp_path):
    rec = _Recorder()
    orch = _orchestrator(tmp_path, rec, _Cloud(rec))
    lines: list[str] = []
    result = orch.provision(
        "Run_1", deploy_cloud=False, instance_id="dep-abc", host_port=8123, log=lines.append
    )
    assert result.image.tag == "dana-mmm-api:dep-abc"
    assert result.container.name == "dana-mmm-dep-abc"
    assert result.container.base_url == "http://127.0.0.1:8123"
    assert orch.runtime.runs == [("dana-mmm-dep-abc", 8123)]
    assert lines[0].startswith("Resolving model run Run_1")
    assert "Starting the container" in lines


def test_orchestrator_deprovision_removes_container(tmp_path):
    rec = _Recorder()
    orch = _orchestrator(tmp_path, rec, _Cloud(rec))
    orch.deprovision("dep-abc")
    assert orch.runtime.removed == ["dana-mmm-dep-abc"]
