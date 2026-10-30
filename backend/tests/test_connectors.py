import asyncio
import functools
import math
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from psycopg import sql

from integrations.connectors import catalog
from integrations.connectors.catalog import _estimate, _jsonable, get_connector_page, list_connectors
from tests.test_api import ORG_A, ORG_B, auth, client, member, mint, raw_db, settings  # noqa: F401


def run(coro_fn):
    @functools.wraps(coro_fn)
    def wrapper():
        asyncio.run(coro_fn())

    return wrapper


class _Scope:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


class FakeDB:
    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def answer(self, text, params):
        self.queries.append((text, params))
        if "information_schema.tables" in text:
            return [{"table_name": n, "row_estimate": t["estimate"]} for n, t in sorted(self.tables.items())]
        if "table_name = %s" in text:
            table = self.tables.get(params[1])
            return [{"column_name": c, "data_type": d} for c, d in table["columns"]] if table else []
        if "information_schema.columns" in text:
            return [
                {"table_name": n, "column_name": c, "data_type": d}
                for n, t in sorted(self.tables.items())
                for c, d in t["columns"]
            ]
        if "COUNT(_d" in text:
            return [{f"_n{part[0]}": 0 for part in text.split("COUNT(_d")[1:]}]
        name = next(n for n in self.tables if f'"{n}"' in text)
        rows = self.tables[name]["rows"]
        if " WHERE " in text:
            rows = [row for row in rows if row["org_id"] == params[0]]
        if "count(*)" in text:
            return [{"total": len(rows)}]
        limit, offset = params[-2], params[-1]
        return rows[offset : offset + limit]


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = []

    async def execute(self, query, params=()):
        text = query.as_string(None) if isinstance(query, sql.Composed) else query
        self.result = self.db.answer(text, tuple(params))

    async def fetchall(self):
        return self.result

    async def fetchone(self):
        return self.result[0]


class FakeConn:
    def __init__(self, db):
        self.db = db

    def transaction(self):
        return _Scope(None)

    def cursor(self, row_factory=None):
        return _Scope(FakeCursor(self.db))


class FakePool:
    def __init__(self, db):
        self.db = db

    def connection(self):
        return _Scope(FakeConn(self.db))

    async def close(self):
        return None


def sample_db():
    return FakeDB(
        {
            "sheet_meta": {
                "estimate": 3,
                "columns": [("org_id", "text"), ("week", "date"), ("spend", "numeric")],
                "rows": [
                    {"org_id": ORG_A, "week": date(2024, 1, 1), "spend": Decimal("10.5")},
                    {"org_id": ORG_B, "week": date(2024, 1, 1), "spend": Decimal("99")},
                    {"org_id": ORG_A, "week": date(2024, 1, 8), "spend": Decimal("12")},
                ],
            },
            "sheet_plain": {
                "estimate": -1,
                "columns": [("channel", "text"), ("value", "double precision")],
                "rows": [
                    {"channel": "search", "value": 1.5},
                    {"channel": "social", "value": float("nan")},
                    {"channel": "tv", "value": 3.0},
                ],
            },
        }
    )


def test_jsonable_converts_database_types():
    assert _jsonable(Decimal("1.25")) == "1.25"
    assert _jsonable(UUID("12345678-1234-5678-1234-567812345678")) == "12345678-1234-5678-1234-567812345678"
    assert _jsonable(datetime(2024, 1, 2, 3, 4)) == "2024-01-02T03:04:00"
    assert _jsonable(date(2024, 1, 2)) == "2024-01-02"
    assert _jsonable(b"abc") == "<3 bytes>"
    assert _jsonable(math.nan) is None
    assert _jsonable({"a": [Decimal("2")]}) == {"a": ["2"]}


def test_estimate_hides_unanalyzed_tables():
    assert _estimate(-1) is None
    assert _estimate(None) is None
    assert _estimate(0) == 0
    assert _estimate(42) == 42


@run
async def test_list_connectors_reports_row_estimates_and_org_scope():
    connectors = await list_connectors(FakePool(sample_db()), "datasets")

    assert [c["name"] for c in connectors] == ["sheet_meta", "sheet_plain"]
    assert connectors[0]["row_estimate"] == 3
    assert connectors[0]["org_scoped"] is True
    assert connectors[1]["row_estimate"] is None
    assert connectors[1]["org_scoped"] is False
    assert connectors[1]["columns"] == [
        {"name": "channel", "data_type": "text"},
        {"name": "value", "data_type": "double precision"},
    ]


@run
async def test_page_is_scoped_to_the_callers_org():
    db = sample_db()
    page = await get_connector_page(FakePool(db), "datasets", "sheet_meta", ORG_A, 1, 50)

    assert page["org_scoped"] is True
    assert page["total_rows"] == 2
    assert all(row[0] == ORG_A for row in page["rows"])
    assert [row[2] for row in page["rows"]] == ["10.5", "12"]
    scoped_queries = [q for q, _ in db.queries if "count(*)" in q or "ORDER BY ctid" in q]
    assert scoped_queries and all('WHERE "org_id"::text = %s' in q for q in scoped_queries)


@run
async def test_table_without_org_column_is_not_filtered():
    page = await get_connector_page(FakePool(sample_db()), "datasets", "sheet_plain", ORG_A, 1, 50)

    assert page["org_scoped"] is False
    assert page["total_rows"] == 3
    assert page["rows"][1] == ["social", None]


@run
async def test_pagination_reports_pages_and_slices_rows():
    db = FakeDB(
        {
            "sheet_many": {
                "estimate": 5,
                "columns": [("org_id", "text"), ("n", "integer")],
                "rows": [{"org_id": ORG_A, "n": i} for i in range(5)],
            }
        }
    )
    page = await get_connector_page(FakePool(db), "datasets", "sheet_many", ORG_A, 3, 2)

    assert page["total_rows"] == 5
    assert page["total_pages"] == 3
    assert page["rows"] == [[ORG_A, 4]]


@run
async def test_missing_table_returns_none():
    assert await get_connector_page(FakePool(sample_db()), "datasets", "nope", ORG_A, 1, 50) is None


def test_connectors_require_a_token(client):
    assert client.get("/api/v1/connectors").status_code == 401


def test_connectors_return_503_when_database_is_not_configured(client, member):
    response = client.get("/api/v1/connectors", headers=auth(mint()))

    assert response.status_code == 503


def test_rows_return_503_when_database_is_not_configured(client, member):
    response = client.get("/api/v1/connectors/sheet_meta/rows", headers=auth(mint()))

    assert response.status_code == 503


def test_rows_pass_the_principal_org_to_the_catalog(client, member, monkeypatch):
    seen = {}

    async def fake_page(pool, schema, table, org_id, page, page_size):
        seen.update(org_id=org_id, table=table, page=page, page_size=page_size)
        return {
            "name": table,
            "org_scoped": True,
            "columns": [],
            "rows": [],
            "page": page,
            "page_size": page_size,
            "total_rows": 0,
            "total_pages": 1,
        }

    monkeypatch.setattr("api.routes.connectors.get_connector_page", fake_page)
    client.app.state.connector_pool = FakePool(FakeDB({}))

    response = client.get("/api/v1/connectors/sheet_meta/rows?page=2&page_size=10", headers=auth(mint()))

    assert response.status_code == 200
    assert response.json()["org_scoped"] is True
    assert seen == {"org_id": ORG_A, "table": "sheet_meta", "page": 2, "page_size": 10}


def test_rows_return_404_for_unknown_connector(client, member, monkeypatch):
    async def missing(*_args, **_kwargs):
        return None

    monkeypatch.setattr("api.routes.connectors.get_connector_page", missing)
    client.app.state.connector_pool = FakePool(FakeDB({}))

    response = client.get("/api/v1/connectors/ghost/rows", headers=auth(mint()))

    assert response.status_code == 404


def test_rows_reject_out_of_range_paging(client, member):
    client.app.state.connector_pool = FakePool(FakeDB({}))

    assert client.get("/api/v1/connectors/sheet_meta/rows?page=0", headers=auth(mint())).status_code == 422
    assert client.get("/api/v1/connectors/sheet_meta/rows?page_size=500", headers=auth(mint())).status_code == 422


def test_list_endpoint_uses_pool_and_schema(client, member, monkeypatch):
    async def fake_list(pool, schema):
        assert schema == "datasets"
        return [{"name": "sheet_meta", "row_estimate": 3, "org_scoped": True, "columns": []}]

    monkeypatch.setattr("api.routes.connectors.list_connectors", fake_list)
    client.app.state.connector_pool = FakePool(FakeDB({}))

    response = client.get("/api/v1/connectors", headers=auth(mint()))

    assert response.status_code == 200
    assert response.json()[0]["name"] == "sheet_meta"
