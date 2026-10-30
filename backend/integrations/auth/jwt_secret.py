from config.settings import Settings
from integrations.keyvault.client import build_keyvault_reader

JWT_SECRET_NAME = "JWT-MASTER-TOKEN"


def load_jwt_secret(settings: Settings) -> str:
    reader = build_keyvault_reader(settings)
    try:
        return reader.get_secret(JWT_SECRET_NAME)
    finally:
        reader.close()
