from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from api.main import create_app
from config.settings import Settings
from integrations.keyvault.client import KeyVaultNotConfigured

TEST_SECRET = "test-only-secret-0123456789abcdef0123456789"
TEST_DB = "dana_ai_test"
ORG_A = "org-a"
ORG_B = "org-b"
USER_1 = "user-1"
USER_2 = "user-2"


def make_settings(**overrides) -> Settings:
    base = dict(
        mongo_db=TEST_DB,
        jwt_issuer="omnidoc",
        jwt_audience=None,
        jwt_leeway_seconds=0,
    )
    base.update(overrides)
    return Settings(**base)


def static_secret(_settings: Settings) -> str:
    return TEST_SECRET


def mint(
    *,
    secret: str = TEST_SECRET,
    issuer: str | None = "omnidoc",
    typ: str | None = "access",
    org: str | None = ORG_A,
    user: str | None = USER_1,
    expires_in: timedelta = timedelta(hours=1),
    extra: dict | None = None,
    algorithm: str = "HS256",
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {"email": "dev@example.com", "role": "admin", "iat": now, "exp": now + expires_in}
    if issuer is not None:
        payload["iss"] = issuer
    if typ is not None:
        payload["typ"] = typ
    if org is not None:
        payload["organizationId"] = org
    if user is not None:
        payload["userId"] = user
    if extra:
        payload.update(extra)
    key = None if algorithm == "none" else secret
    return jwt.encode(payload, key, algorithm=algorithm)


@pytest.fixture()
def settings() -> Settings:
    return make_settings()


@pytest.fixture()
def raw_db(settings):
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    client.drop_database(TEST_DB)
    yield client[TEST_DB]
    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture()
def client(settings, raw_db):
    with TestClient(create_app(settings, jwt_secret_loader=static_secret)) as c:
        yield c


@pytest.fixture()
def member(raw_db):
    raw_db.memberships.insert_one(
        {"user_id": USER_1, "org_id": ORG_A, "role": "analyst", "status": "active"}
    )


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_ready_reports_mongo_and_blob(client):
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    assert res.json()["checks"] == {"mongo": "ok", "blob": "ok"}


def test_me_requires_bearer(client):
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"secret": "wrong-secret-that-is-long-enough-0123456789"},
        {"issuer": "someone-else"},
        {"issuer": None},
        {"typ": "refresh"},
        {"org": None},
        {"user": None},
        {"expires_in": timedelta(seconds=-60)},
        {"extra": {"aud": "dana-ai"}},
        {"algorithm": "none"},
    ],
    ids=[
        "wrong-secret",
        "wrong-issuer",
        "missing-issuer",
        "refresh-typ",
        "missing-org",
        "missing-user",
        "expired",
        "aud-without-config",
        "alg-none",
    ],
)
def test_invalid_tokens_are_rejected(client, member, token_kwargs):
    res = client.get("/api/v1/me", headers=auth(mint(**token_kwargs)))
    assert res.status_code == 401


def failing_secret(_settings: Settings) -> str:
    raise KeyVaultNotConfigured("missing AZURE_KEYVAULT_URL")


def test_missing_secret_fails_closed(raw_db):
    with TestClient(create_app(make_settings(), jwt_secret_loader=failing_secret)) as c:
        res = c.get("/api/v1/me", headers=auth(mint()))
    assert res.status_code == 503


def test_empty_secret_fails_closed(raw_db):
    with TestClient(create_app(make_settings(), jwt_secret_loader=lambda _s: "")) as c:
        res = c.get("/api/v1/me", headers=auth(mint()))
    assert res.status_code == 503


def test_token_without_membership_is_forbidden(client):
    assert client.get("/api/v1/me", headers=auth(mint())).status_code == 403


def test_inactive_membership_is_forbidden(client, raw_db):
    raw_db.memberships.insert_one(
        {"user_id": USER_1, "org_id": ORG_A, "role": "admin", "status": "suspended"}
    )
    assert client.get("/api/v1/me", headers=auth(mint())).status_code == 403


def test_me_returns_membership_role_not_token_role(client, member):
    res = client.get("/api/v1/me", headers=auth(mint()))
    assert res.status_code == 200
    assert res.json() == {
        "user_id": USER_1,
        "org_id": ORG_A,
        "email": "dev@example.com",
        "role": "analyst",
    }


def test_membership_is_scoped_to_org(client, member):
    assert client.get("/api/v1/me", headers=auth(mint(org=ORG_B))).status_code == 403


def test_chats_are_tenant_isolated(client, member, raw_db):
    now = datetime.now(timezone.utc)
    raw_db.chats.insert_many(
        [
            {"id": "c1", "title": "Mine", "org_id": ORG_A, "user_id": USER_1, "created_at": now, "updated_at": now},
            {"id": "c2", "title": "Other user", "org_id": ORG_A, "user_id": USER_2, "created_at": now, "updated_at": now},
            {"id": "c3", "title": "Other org", "org_id": ORG_B, "user_id": USER_1, "created_at": now, "updated_at": now},
        ]
    )
    res = client.get("/api/v1/chats", headers=auth(mint()))
    assert res.status_code == 200
    assert [c["id"] for c in res.json()] == ["c1"]


def test_jobs_are_tenant_isolated(client, member, raw_db):
    now = datetime.now(timezone.utc)
    raw_db.jobs.insert_many(
        [
            {"id": "j1", "title": "Mine", "kind": "mmm", "status": "queued", "org_id": ORG_A, "user_id": USER_1, "created_at": now, "updated_at": now},
            {"id": "j2", "title": "Other user", "kind": "mmm", "status": "queued", "org_id": ORG_A, "user_id": USER_2, "created_at": now, "updated_at": now},
        ]
    )
    res = client.get("/api/v1/jobs", headers=auth(mint()))
    assert res.status_code == 200
    assert [j["id"] for j in res.json()] == ["j1"]
