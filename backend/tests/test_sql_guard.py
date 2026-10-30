import pytest

from integrations.connectors.sql_guard import SqlRejected, guard_query

ORG = "6aa3cc95c87b31265acea056"
OTHER_ORG = "000000000000000000000001"
TABLES = {"sheet_a": True, "shared_t": False}


def guard(query: str, org: str = ORG, tables: dict | None = None):
    return guard_query(query, schema="datasets", org_id=org, tables=tables or TABLES)


def test_org_scoped_table_is_limited_to_the_signed_in_org():
    result = guard("SELECT MAX(week) FROM sheet_a")
    assert "FROM (SELECT * FROM datasets.sheet_a WHERE CAST(org_id AS TEXT) = '" + ORG + "') AS sheet_a" in result.sql
    assert result.tables == ("sheet_a",)


def test_alias_is_kept_so_column_references_still_work():
    result = guard("SELECT a.week FROM sheet_a AS a WHERE a.week > '2024-01-01'")
    assert "AS a WHERE a.week" in result.sql


def test_shared_table_is_qualified_but_not_scoped():
    result = guard("SELECT * FROM shared_t")
    assert result.sql == "SELECT * FROM datasets.shared_t"


def test_cte_over_connector_tables_is_scoped_inside_the_cte():
    result = guard("WITH x AS (SELECT * FROM sheet_a) SELECT COUNT(*) FROM x")
    assert "datasets.sheet_a WHERE CAST(org_id AS TEXT)" in result.sql
    assert result.tables == ("sheet_a",)


def test_union_is_allowed():
    assert guard("SELECT 1 UNION SELECT 2").tables == ()


def test_trailing_semicolon_is_allowed():
    assert guard("SELECT MAX(week) FROM sheet_a;").tables == ("sheet_a",)


@pytest.mark.parametrize(
    "query, reason",
    [
        ("DELETE FROM sheet_a", "Only SELECT"),
        ("UPDATE sheet_a SET week = 'x'", "Only SELECT"),
        ("COPY sheet_a TO '/tmp/x'", "Only SELECT"),
        ("SELECT 1; DROP TABLE sheet_a", "exactly one"),
        ("SELECT * INTO newt FROM sheet_a", "read-only"),
        ("SELECT * FROM sheet_a FOR UPDATE", "read-only"),
        ("SELECT * FROM pg_catalog.pg_tables", "datasets schema"),
        ("SELECT * FROM information_schema.tables", "datasets schema"),
        ("SELECT * FROM other_schema.sheet_a", "datasets schema"),
        ("SELECT * FROM users", "Unknown table users"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file is not allowed"),
        ("SELECT dblink('x', 'select 1')", "dblink is not allowed"),
        ("SELECT set_config('x', 'y', false)", "set_config is not allowed"),
        ("WITH sheet_a AS (SELECT * FROM sheet_a) SELECT * FROM sheet_a", "WITH name"),
        ("", "empty"),
    ],
)
def test_unsafe_queries_are_refused(query, reason):
    with pytest.raises(SqlRejected, match=reason):
        guard(query)


def test_org_id_must_be_a_plain_identifier():
    with pytest.raises(SqlRejected, match="not valid"):
        guard("SELECT 1", org="x' OR '1'='1")


def test_overlong_query_is_refused():
    with pytest.raises(SqlRejected, match="longer than"):
        guard("SELECT 1 " + "+ 1 " * 2000)
