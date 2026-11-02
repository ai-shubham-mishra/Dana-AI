from typing import Any

import httpx

HEALTH_TIMEOUT_S = 2.0


async def probe(client: httpx.AsyncClient, base_url: str) -> dict[str, Any]:
    try:
        response = await client.get(f"{base_url}/health", timeout=HEALTH_TIMEOUT_S)
    except httpx.HTTPError as exc:
        return {"state": "unreachable", "detail": type(exc).__name__}
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200 and isinstance(body, dict) and body.get("model_loaded") is not False:
        return {"state": "live", "detail": "Health check passed"}
    return {"state": "unhealthy", "detail": f"HTTP {response.status_code}"}
