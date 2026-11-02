"""Azure Resource Manager client for Microsoft.App/containerApps. Point base_url at WireMock for local runs."""

from __future__ import annotations

import time
from typing import Any

import httpx

from integrations.provisioning.models import ProvisionedApp

API_VERSION = "2024-03-01"
_TERMINAL_FAILURES = {"Failed", "Canceled"}


class ArmError(RuntimeError):
    pass


class ContainerAppsClient:
    def __init__(
        self,
        base_url: str,
        subscription_id: str,
        resource_group: str,
        location: str,
        managed_environment_id: str,
        token: str,
        http: httpx.Client | None = None,
        poll_interval_s: float = 2.0,
        timeout_s: float = 600.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        self.managed_environment_id = managed_environment_id
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._http = http or httpx.Client()
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s

    def app_url(self, name: str) -> str:
        return (
            f"{self.base_url}/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.App/containerApps/{name}?api-version={API_VERSION}"
        )

    def deploy(self, name: str, image: str, container_port: int, env: dict[str, str]) -> ProvisionedApp:
        url = self.app_url(name)
        response = self._http.put(url, json=self._body(name, image, container_port, env), headers=self._headers)
        if response.status_code not in (200, 201, 202):
            raise ArmError(f"PUT {name} failed: HTTP {response.status_code} {response.text[:500]}")
        operation = response.headers.get("Azure-AsyncOperation")
        if operation:
            self._wait_operation(operation)
        return self._read_app(name, url)

    def _body(self, name: str, image: str, container_port: int, env: dict[str, str]) -> dict[str, Any]:
        return {
            "location": self.location,
            "properties": {
                "managedEnvironmentId": self.managed_environment_id,
                "configuration": {
                    "ingress": {"external": True, "targetPort": container_port, "transport": "auto"},
                },
                "template": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "env": [{"name": k, "value": v} for k, v in env.items()],
                            "resources": {"cpu": 1, "memory": "2Gi"},
                        }
                    ],
                    "scale": {"minReplicas": 1, "maxReplicas": 1},
                },
            },
        }

    def _wait_operation(self, operation_url: str) -> None:
        deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < deadline:
            body = self._get_json(operation_url)
            status = body.get("status")
            if status == "Succeeded":
                return
            if status in _TERMINAL_FAILURES:
                raise ArmError(f"Container app operation {status}: {body.get('error', body)}")
            time.sleep(self._poll_interval_s)
        raise ArmError(f"Container app operation timed out after {self._timeout_s:.0f}s")

    def _read_app(self, name: str, url: str) -> ProvisionedApp:
        body = self._get_json(url)
        props = body.get("properties", {})
        fqdn = props.get("configuration", {}).get("ingress", {}).get("fqdn")
        return ProvisionedApp(name=name, fqdn=fqdn, provisioning_state=props.get("provisioningState"))

    def _get_json(self, url: str) -> dict[str, Any]:
        response = self._http.get(url, headers=self._headers)
        if response.status_code != 200:
            raise ArmError(f"GET failed: HTTP {response.status_code} {response.text[:500]}")
        return response.json()
