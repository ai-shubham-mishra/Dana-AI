from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from integrations.auth.jwt_verifier import TokenError, verify_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    org_id: str
    email: str | None
    role: str


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    secret = request.app.state.jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    try:
        claims = verify_access_token(credentials.credentials, secret, request.app.state.settings)
    except TokenError as exc:
        raise unauthorized from exc

    membership = await request.app.state.db.memberships.find_one(
        {"user_id": claims.user_id, "org_id": claims.org_id, "status": "active"},
        {"role": 1, "_id": 0},
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership in this organization",
        )

    return Principal(
        user_id=claims.user_id,
        org_id=claims.org_id,
        email=claims.email,
        role=membership.get("role", "member"),
    )
