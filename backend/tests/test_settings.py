import jwt
import pytest

from config.settings import Settings
from integrations.auth.jwt_verifier import TokenError, verify_access_token

SECRET = "test-only-secret-0123456789abcdef0123456789"


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_jwt_audience_is_treated_as_unset(monkeypatch, raw):
    monkeypatch.setenv("JWT_AUDIENCE", raw)
    assert Settings(_env_file=None).jwt_audience is None


def test_blank_audience_accepts_token_without_aud_claim(monkeypatch):
    monkeypatch.setenv("JWT_AUDIENCE", "")
    settings = Settings(_env_file=None)
    token = jwt.encode(
        {"iss": "omnidoc", "exp": 4102444800, "userId": "u", "organizationId": "o", "typ": "access"},
        SECRET,
        algorithm="HS256",
    )
    assert verify_access_token(token, SECRET, settings).user_id == "u"


def test_configured_audience_is_still_enforced(monkeypatch):
    monkeypatch.setenv("JWT_AUDIENCE", "dana-ai")
    settings = Settings(_env_file=None)
    token = jwt.encode(
        {"iss": "omnidoc", "exp": 4102444800, "userId": "u", "organizationId": "o", "typ": "access"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        verify_access_token(token, SECRET, settings)
