from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError

from config.settings import Settings

ALGORITHM = "HS256"
ACCEPTED_TYP = {None, "access"}


class TokenError(Exception):
    pass


class SecretNotConfigured(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    org_id: str
    email: str | None
    token_role: str | None


def _required_str(claims: dict, key: str) -> str:
    value = claims.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TokenError(f"Missing claim: {key}")
    return value


def verify_access_token(token: str, settings: Settings) -> TokenClaims:
    if settings.jwt_master_token is None or not settings.jwt_master_token.get_secret_value():
        raise SecretNotConfigured()

    try:
        claims = jwt.decode(
            token,
            settings.jwt_master_token.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            leeway=settings.jwt_leeway_seconds,
            options={"require": ["exp", "iss"]},
        )
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if claims.get("typ") not in ACCEPTED_TYP:
        raise TokenError("Token type is not an access token")

    email = claims.get("email")
    role = claims.get("role")
    return TokenClaims(
        user_id=_required_str(claims, "userId"),
        org_id=_required_str(claims, "organizationId"),
        email=email if isinstance(email, str) else None,
        token_role=role if isinstance(role, str) else None,
    )
