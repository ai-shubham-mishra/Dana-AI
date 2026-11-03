from azure.core.exceptions import ResourceNotFoundError
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient

from config.settings import Settings


class KeyVaultError(RuntimeError):
    pass


class KeyVaultNotConfigured(KeyVaultError):
    pass


class KeyVaultSecretNotFound(KeyVaultError):
    pass


class KeyVaultReader:
    """Read-only access to Key Vault secrets. Only get_secret is exposed; no writes or listing."""

    def __init__(self, vault_url: str, tenant_id: str, client_id: str, client_secret: str) -> None:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self._client = SecretClient(vault_url=vault_url, credential=credential)
        self._cache: dict[str, str] = {}

    def get_secret(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]
        try:
            value = self._client.get_secret(name).value
        except ResourceNotFoundError as exc:
            raise KeyVaultSecretNotFound(f"Key Vault secret '{name}' is missing") from exc
        if not value:
            raise KeyVaultSecretNotFound(f"Key Vault secret '{name}' is empty")
        self._cache[name] = value
        return value

    def close(self) -> None:
        self._client.close()


def build_keyvault_reader(settings: Settings) -> KeyVaultReader:
    missing = [
        name
        for name, value in (
            ("AZURE_KEYVAULT_URL", settings.azure_keyvault_url),
            ("AZURE_TENANT_ID", settings.azure_tenant_id),
            ("AZURE_CLIENT_ID", settings.azure_client_id),
            ("AZURE_CLIENT_SECRET", settings.azure_client_secret),
        )
        if not value
    ]
    if missing:
        raise KeyVaultNotConfigured(f"Key Vault is not configured; missing: {', '.join(missing)}")
    return KeyVaultReader(
        vault_url=settings.azure_keyvault_url,
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret.get_secret_value(),
    )
