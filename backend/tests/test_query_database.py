import asyncio
import os

import psycopg
import pytest

from agent.tools.db_ops import query_database as module
from agent.tools.db_ops.query_database import QueryDatabaseTool
from integrations.connectors.query import QueryResult
from integrations.training.scope import JobScope, bind_scope

ORG_A = "6aa3cc95c87b31265acea056"
CONNECTORS = [
    {"name": "sheet_a", "org_scoped": True, "columns": [], "row_estimate": 10},
    {"name": "shared_t", "org_scoped": False, "columns": [], "row_estimate": 3},
]


def scoped(org_id: str = ORG_A) -> None:
    bind_scope(JobScope(service=None, org_id=org_id, user_id="user-1", chat_id="chat-1"))


def run(query: str) -> str:
    tool = QueryDatabaseTool(pool=object(), datasets_schema="datasets")
    try:
        return asyncio.run(tool.ainvoke({"query": query}))
    finally:
        bind_scope(None)


@pytest.fixture
def fake_db(monkeypatch):
    calls = {}

    async def connectors(pool, schema):
        return CONNECTORS

    async def run_query(pool, sql, row_limit=200):
        calls["sql"] = sql
        return QueryResult(columns=["latest"], rows=[("2025-11-30",)], truncated=False)

    monkeypatch.setattr(module, "list_connectors", connectors)
    monkeypatch.setattr(module, "run_readonly_query", run_query)
    return calls


def test_query_runs_scoped_and_returns_a_markdown_table(fake_db):
    scoped()
    out = run("SELECT MAX(date) AS latest FROM sheet_a")
    assert "| latest |" in out and "| 2025-11-30 |" in out
    assert ORG_A in fake_db["sql"]


def test_refused_query_never_reaches_the_database(monkeypatch):
    async def must_not_run(pool, sql, row_limit=200):
        raise AssertionError("the database must not be called")

    async def connectors(pool, schema):
        return CONNECTORS

    monkeypatch.setattr(module, "run_readonly_query", must_not_run)
    monkeypatch.setattr(module, "list_connectors", connectors)
    scoped()
    assert run("DELETE FROM sheet_a").startswith("Error: Only SELECT")


def test_query_needs_a_signed_in_scope(fake_db):
    assert "no organization" in run("SELECT 1")


def test_timeout_is_reported_in_plain_language(monkeypatch):
    async def slow(pool, sql, row_limit=200):
        raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")

    async def connectors(pool, schema):
        return CONNECTORS

    monkeypatch.setattr(module, "run_readonly_query", slow)
    monkeypatch.setattr(module, "list_connectors", connectors)
    scoped()
    assert "15 second limit" in run("SELECT MAX(date) FROM sheet_a")


DATABASE_URL = os.getenv("DATABASE_URL_TEST")


@pytest.mark.skipif(not DATABASE_URL, reason="set DATABASE_URL_TEST to run against the connector database")
def test_real_database_latest_date_is_scoped_to_the_org():
    from config.settings import get_settings
    from integrations.connectors.catalog import list_connectors
    from integrations.postgres.client import create_readonly_pool

    async def check():
        pool = create_readonly_pool(get_settings().database_url_test.get_secret_value())
        await pool.open()
        try:
            tool = QueryDatabaseTool(pool=pool, datasets_schema="datasets")
            sheet = next(c["name"] for c in await list_connectors(pool, "datasets") if c["org_scoped"])
            query = f"SELECT COUNT(*) AS rows_for_org FROM {sheet}"
            scoped(ORG_A)
            mine = await tool.ainvoke({"query": query})
            scoped("000000000000000000000001")
            other = await tool.ainvoke({"query": query})
            return mine, other
        finally:
            bind_scope(None)
            await pool.close()

    mine, other = asyncio.run(check())
    assert not mine.startswith("Error")
    assert int(mine.splitlines()[-1].strip("| ")) > 0
    assert other.splitlines()[-1].strip("| ") == "0"
