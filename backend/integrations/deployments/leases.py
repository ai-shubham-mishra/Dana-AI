from collections.abc import Callable
from datetime import UTC, datetime
import socket

from pymongo.errors import DuplicateKeyError


class NoPortAvailable(RuntimeError):
    pass


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


class PortLeases:
    """Hands out host ports from a range. A port is taken when its _id is inserted, so two deployments can't share one."""

    def __init__(self, db, port_range: range, is_free: Callable[[int], bool] = _port_is_free):
        self._leases = db.port_leases
        self._ports = port_range
        self._is_free = is_free

    async def acquire(self, owner: str) -> int:
        for port in self._ports:
            if not self._is_free(port):
                continue
            try:
                await self._leases.insert_one({"_id": port, "owner": owner, "created_at": datetime.now(UTC)})
            except DuplicateKeyError:
                continue
            return port
        raise NoPortAvailable(f"no free port in {self._ports.start}-{self._ports.stop - 1}")

    async def release(self, owner: str) -> None:
        await self._leases.delete_many({"owner": owner})
