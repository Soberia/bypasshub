from typing import Annotated

from fastapi import APIRouter, Depends

from .user import user_not_exist_response_model
from ..dependencies import get_manager, validate_username
from ...managers import Manager
from ...types import Credentials, Plan, Traffic

router = APIRouter(prefix="/info")


@router.get("/users", tags=["info"], summary="The list of all the users")
async def users(manager: Annotated[Manager, Depends(get_manager)]) -> list[str]:
    return manager.usernames


@router.get("/capacity", tags=["info"], summary="The count of all the users")
async def capacity(manager: Annotated[Manager, Depends(get_manager)]) -> int:
    return manager.capacity


@router.get(
    "/active-capacity",
    tags=["info"],
    summary="The count of all the users that have an active plan",
)
async def active_capacity(manager: Annotated[Manager, Depends(get_manager)]) -> int:
    return manager.active_capacity


@router.get(
    "/credentials",
    tags=["info"],
    summary="The user's credentials",
    responses=user_not_exist_response_model,
)
async def credentials(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> Credentials:
    return manager.get_credentials(username)


@router.get(
    "/plan",
    tags=["info"],
    summary="The user's plan",
    responses=user_not_exist_response_model,
)
async def plan(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> Plan:
    return manager.get_plan(username)


@router.get(
    "/total-traffic",
    tags=["info"],
    summary="The user's total traffic consumption in bytes",
    responses=user_not_exist_response_model,
)
async def total_traffic(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> Traffic:
    return manager.get_total_traffic(username)


@router.get(
    "/is-exist",
    tags=["info"],
    summary="Whether the user exists in the database",
    responses=user_not_exist_response_model,
)
async def is_exist(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.is_exist(username)


@router.get(
    "/has-active-plan",
    tags=["info"],
    summary=(
        "Whether the user has an active plan"
        " (A plan is considered active when still has time and traffic)"
    ),
    responses=user_not_exist_response_model,
)
async def has_active_plan(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.has_active_plan(username)


@router.get(
    "/has-unlimited-time",
    tags=["info"],
    summary="Whether the user has an unrestricted time plan",
    responses=user_not_exist_response_model,
)
async def has_unlimited_time(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.has_unlimited_time_plan(username)


@router.get(
    "/has-unlimited-traffic",
    tags=["info"],
    summary="Whether the user has an unrestricted traffic plan",
    responses=user_not_exist_response_model,
)
async def has_unlimited_traffic(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.has_unlimited_traffic_plan(username)
