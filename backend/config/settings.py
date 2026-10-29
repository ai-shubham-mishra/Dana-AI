from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    mongo_uri: str = "mongodb://dana:dana-dev-password@localhost:27017/?authSource=admin"
    mongo_db: str = "dana_ai"

    jwt_issuer: str = "omnidoc"
    jwt_audience: str | None = None
    jwt_leeway_seconds: int = 0

    @field_validator("jwt_audience", mode="before")
    @classmethod
    def _blank_audience_is_unset(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # Read-only connector database. Holds one table per connector in datasets_schema.
    # Treated as the org database for now; per-org routing comes later.
    database_url_test: SecretStr | None = None
    datasets_schema: str = "datasets"

    blob_connection_string: str = "UseDevelopmentStorage=true"
    blob_container: str = "dana-ai-files"

    # Key Vault bootstrap (read-only service principal). Secrets are never read from .env.
    # The JWT verification secret is JWT-MASTER-TOKEN in Key Vault (see integrations/auth/jwt_secret.py).
    azure_keyvault_url: str | None = None
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: SecretStr | None = None

    llm_model: str = "claude-sonnet-5-5"
    agent_root: Path = BACKEND_ROOT / "agent"

    training_output_dir: Path = BACKEND_ROOT / "var" / "training"
    training_mmm_dir: Path = BACKEND_ROOT / "resources" / "training" / "mmm"


@lru_cache
def get_settings() -> Settings:
    return Settings()
