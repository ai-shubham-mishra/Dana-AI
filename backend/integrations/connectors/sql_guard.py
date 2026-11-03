import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from integrations.connectors.catalog import ORG_COLUMN

MAX_QUERY_CHARS = 4000
ORG_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
_FORBIDDEN_NODE_NAMES = (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "TruncateTable", "Command",
    "Into", "Lock", "Copy", "Set", "Transaction", "Commit", "Rollback", "Pragma", "Use", "Grant", "Revoke",
)
_FORBIDDEN_NODES = tuple(node for node in (getattr(exp, name, None) for name in _FORBIDDEN_NODE_NAMES) if node)
_FORBIDDEN_FUNCTION_PREFIXES = ("pg_", "lo_")
_FORBIDDEN_FUNCTIONS = frozenset({"dblink", "dblink_exec", "set_config", "current_setting"})


class SqlRejected(ValueError):
    """The query was refused before it reached the database. The message is safe to show the agent."""


@dataclass(frozen=True)
class GuardedQuery:
    sql: str
    tables: tuple[str, ...]


def guard_query(query: str, *, schema: str, org_id: str, tables: dict[str, bool]) -> GuardedQuery:
    """Check a read-only SELECT and rewrite it so every connector read is limited to one org.

    tables maps each connector table name to whether it carries an org_id column.
    """
    text = (query or "").strip().rstrip(";").strip()
    if not text:
        raise SqlRejected("The query is empty.")
    if len(text) > MAX_QUERY_CHARS:
        raise SqlRejected(f"The query is longer than {MAX_QUERY_CHARS} characters.")
    if not ORG_ID_PATTERN.fullmatch(org_id or ""):
        raise SqlRejected("The organization id is not valid, so the query cannot be scoped.")

    try:
        statements = [statement for statement in sqlglot.parse(text, read="postgres") if statement is not None]
    except SqlglotError as exc:
        raise SqlRejected(f"The query could not be parsed as PostgreSQL: {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise SqlRejected("Send exactly one SELECT statement.")
    root = statements[0]
    if not isinstance(root, exp.Select | exp.Union):
        raise SqlRejected("Only SELECT queries are allowed.")
    if any(True for _ in root.find_all(*_FORBIDDEN_NODES)):
        raise SqlRejected("Only read-only SELECT queries are allowed.")

    for func in root.find_all(exp.Func):
        name = str(func.this).lower() if isinstance(func, exp.Anonymous) else func.sql_name().lower()
        if name.startswith(_FORBIDDEN_FUNCTION_PREFIXES) or name in _FORBIDDEN_FUNCTIONS:
            raise SqlRejected(f"The function {name} is not allowed.")

    lookup = {name.lower(): name for name in tables}
    cte_names = {cte.alias.lower() for cte in root.find_all(exp.CTE) if cte.alias}
    if cte_names & lookup.keys():
        raise SqlRejected("A WITH name cannot match a connector table name. Rename the WITH clause.")
    read: list[str] = []
    for table in list(root.find_all(exp.Table)):
        if not table.name:
            continue
        if not table.db and table.name.lower() in cte_names:
            continue
        if table.catalog or (table.db and table.db.lower() != schema.lower()):
            raise SqlRejected(f"Only tables in the {schema} schema can be queried.")
        real_name = lookup.get(table.name.lower())
        if real_name is None:
            raise SqlRejected(f"Unknown table {table.name}. Use list_connectors to see the available tables.")
        read.append(real_name)
        alias = table.alias or real_name
        if tables[real_name]:
            table.replace(_org_scoped_subquery(real_name, schema, org_id, alias))
        else:
            table.set("db", exp.to_identifier(schema))
            table.set("this", exp.to_identifier(real_name))

    return GuardedQuery(sql=root.sql(dialect="postgres"), tables=tuple(dict.fromkeys(read)))


def _org_scoped_subquery(table: str, schema: str, org_id: str, alias: str) -> exp.Subquery:
    inner = (
        exp.select("*")
        .from_(exp.Table(this=exp.to_identifier(table), db=exp.to_identifier(schema)))
        .where(
            exp.EQ(
                this=exp.Cast(this=exp.column(ORG_COLUMN), to=exp.DataType.build("text")),
                expression=exp.Literal.string(org_id),
            )
        )
    )
    return exp.Subquery(this=inner, alias=exp.TableAlias(this=exp.to_identifier(alias)))
