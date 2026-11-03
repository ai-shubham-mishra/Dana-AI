from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from psycopg import OperationalError
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import BaseModel

from integrations.auth.dependencies import Principal, get_principal
from integrations.connectors.catalog import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    get_connector_page,
    list_connectors,
)

router = APIRouter(prefix="/api/v1/connectors")

NAME_MAX = 128


class ColumnOut(BaseModel):
    name: str
    data_type: str


class ConnectorOut(BaseModel):
    name: str
    row_estimate: int | None
    org_scoped: bool
    columns: list[ColumnOut]


class ConnectorPageOut(BaseModel):
    name: str
    org_scoped: bool
    columns: list[ColumnOut]
    rows: list[list[Any]]
    page: int
    page_size: int
    total_rows: int
    total_pages: int


def _pool(request: Request) -> AsyncConnectionPool:
    pool = request.app.state.connector_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="Connector database is not configured")
    return pool


@router.get("", response_model=list[ConnectorOut])
async def get_connectors(
    request: Request,
    _: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    try:
        return await list_connectors(_pool(request), request.app.state.settings.datasets_schema)
    except (OperationalError, PoolTimeout) as exc:
        raise HTTPException(status_code=503, detail="Connector database is unavailable") from exc


@router.get("/{name}/rows", response_model=ConnectorPageOut)
async def get_connector_rows(
    request: Request,
    name: Annotated[str, Path(min_length=1, max_length=NAME_MAX)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    try:
        found = await get_connector_page(
            _pool(request),
            request.app.state.settings.datasets_schema,
            name,
            principal.org_id,
            page,
            page_size,
        )
    except (OperationalError, PoolTimeout) as exc:
        raise HTTPException(status_code=503, detail="Connector database is unavailable") from exc
    if found is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return found
