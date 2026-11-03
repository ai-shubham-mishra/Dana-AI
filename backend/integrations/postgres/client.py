from psycopg_pool import AsyncConnectionPool

STATEMENT_TIMEOUT_MS = 15000
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4


def create_readonly_pool(url: str) -> AsyncConnectionPool:
    options = f"-c default_transaction_read_only=on -c statement_timeout={STATEMENT_TIMEOUT_MS}"
    return AsyncConnectionPool(
        conninfo=url,
        min_size=POOL_MIN_SIZE,
        max_size=POOL_MAX_SIZE,
        open=False,
        kwargs={"autocommit": True, "application_name": "dana-ai", "options": options},
    )
