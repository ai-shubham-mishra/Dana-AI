from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter()


@router.get("/health")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/health/ready")
async def readiness(request: Request) -> dict:
    checks: dict[str, str] = {}
    try:
        await request.app.state.mongo.admin.command("ping")
        checks["mongo"] = "ok"
    except Exception:
        checks["mongo"] = "unavailable"

    try:
        await request.app.state.blob.get_service_properties()
        checks["blob"] = "ok"
    except Exception:
        checks["blob"] = "unavailable"

    if any(value != "ok" for value in checks.values()):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)
    return {"status": "ready", "checks": checks}
