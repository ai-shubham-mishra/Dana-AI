"""Runs the provisioning flow: resolve model, clone library, build image, run container, deploy app."""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from integrations.provisioning.arm_client import ContainerAppsClient
from integrations.provisioning.build_context import prepare_build_context
from integrations.provisioning.config import ProvisioningConfig
from integrations.provisioning.docker_runtime import DockerCli
from integrations.provisioning.git_source import GitSourceCloner
from integrations.provisioning.model_source import LocalTrainingModelSource
from integrations.provisioning.models import ProvisionResult
from integrations.provisioning.ports import (
    CloudProvisioner,
    ContainerRuntime,
    ImageBuilder,
    LogSink,
    ModelSource,
    SourceCloner,
)

DOCKERFILE = "Dockerfile.api"
LOCAL_ENV = {"MMM_MODEL_SOURCE": "local"}


def _slug(run_id: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "-", run_id.lower())


def _app_name(run_id: str) -> str:
    return ("mmm-" + re.sub(r"[^a-z0-9]", "", run_id.lower()))[:32].rstrip("-")


class ProvisioningOrchestrator:
    def __init__(
        self,
        config: ProvisioningConfig,
        cloner: SourceCloner,
        model_source: ModelSource,
        builder: ImageBuilder,
        runtime: ContainerRuntime,
        cloud: CloudProvisioner,
    ) -> None:
        self.config = config
        self.cloner = cloner
        self.model_source = model_source
        self.builder = builder
        self.runtime = runtime
        self.cloud = cloud

    def provision(
        self,
        run_id: str,
        deploy_cloud: bool = True,
        *,
        instance_id: str | None = None,
        host_port: int | None = None,
        log: LogSink | None = None,
    ) -> ProvisionResult:
        instance = _slug(instance_id or run_id)
        if log:
            log(f"Resolving model run {run_id}")
        model = self.model_source.resolve(run_id)
        if log:
            log("Cloning the MMM library")
        checkout = self.cloner.checkout()
        if log:
            log(f"Library at {checkout.sha[:12]}; preparing build context")
        context_dir = prepare_build_context(
            checkout.library_dir, model, self.config.workdir / "builds" / instance / "context"
        )
        if log:
            log("Building the container image")
        image = self.builder.build(context_dir, DOCKERFILE, f"{self.config.image_repo}:{instance}", log=log)
        if log:
            log("Starting the container")
        container = self.runtime.run(
            image, self.container_name(instance), LOCAL_ENV, self.config.container_port, host_port=host_port
        )
        health = self.runtime.wait_healthy(
            container, self.config.health_timeout_s, self.config.health_interval_s, log=log
        )

        app = None
        warnings: list[str] = []
        if deploy_cloud:
            app = self.cloud.deploy(_app_name(run_id), image.tag, self.config.container_port, LOCAL_ENV)
            warnings.append("Cloud step uses the local image tag; push the image to a registry before a real deploy.")
        return ProvisionResult(
            run_id=run_id,
            source_sha=checkout.sha,
            image=image,
            container=container,
            health=health,
            app=app,
            warnings=warnings,
        )

    @staticmethod
    def container_name(instance_id: str) -> str:
        return f"dana-mmm-{_slug(instance_id)}"

    def deprovision(self, instance_id: str) -> None:
        self.runtime.remove(self.container_name(instance_id))



def build_default_orchestrator(config: ProvisioningConfig) -> ProvisioningOrchestrator:
    http = httpx.Client()
    return ProvisioningOrchestrator(
        config=config,
        cloner=GitSourceCloner(
            repo_url=config.repo_url,
            branch=config.repo_branch,
            library_subdir=config.library_subdir,
            dest=config.workdir / "source",
            token=config.github_token,
        ),
        model_source=LocalTrainingModelSource(Path(config.training_root)),
        builder=DockerCli(http=http),
        runtime=DockerCli(http=http),
        cloud=ContainerAppsClient(
            base_url=config.arm_base_url,
            subscription_id=config.subscription_id,
            resource_group=config.resource_group,
            location=config.location,
            managed_environment_id=config.managed_environment_id,
            token=config.azure_token,
            http=http,
        ),
    )
