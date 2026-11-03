from azure.core.exceptions import ResourceExistsError
from azure.storage.blob.aio import BlobServiceClient


def create_blob_service(connection_string: str) -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(connection_string)


async def ensure_container(service: BlobServiceClient, name: str) -> None:
    try:
        await service.get_container_client(name).create_container()
    except ResourceExistsError:
        pass
