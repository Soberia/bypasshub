from typing import Annotated

from fastapi import APIRouter, Query, Depends
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ..dependencies import get_manager
from ...managers import Manager
from ...database import Database
from ...errors import SynchronizationError
from ...type import DatabaseSchema, HTTPSerializedError

router = APIRouter(prefix="/database")


@router.get(
    "/sync",
    tags=["database"],
    summary="Manually synchronizes the services with the database",
    response_description="Whether the synchronization is performed",
    responses={
        HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        "failed to reflect database changes to services": {
                            "value": {"details": [SynchronizationError().serialize()]},
                        },
                    }
                }
            },
        }
    },
)
async def sync(manager: Annotated[Manager, Depends(get_manager)]) -> bool:
    return await manager.sync()


@router.get("/dump", tags=["database"], summary="Dumps the database")
def dump() -> DatabaseSchema:
    return Database.dump()


@router.get(
    "/backup",
    tags=["database"],
    summary="Generates and stores a database backup",
)
def backup(
    suffix: Annotated[
        str | None,
        Query(
            description=(
                "The backup file name suffix."
                " If not specified, `%timestamp%.bak` will be used."
            )
        ),
    ] = None
) -> "None":
    Database.backup(suffix and f".{suffix}")
