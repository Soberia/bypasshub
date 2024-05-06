from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from .user import user_not_exist_response_model
from ..dependencies import get_manager, validate_username
from ...managers import Manager
from ...types import Credentials, Plan, ReservedPlan, PlanHistory, Traffic

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
    "/reserved-plan",
    tags=["info"],
    summary="The user's reserved plan",
    responses=user_not_exist_response_model,
)
async def reserved_plan(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> ReservedPlan | None:
    return manager.get_reserved_plan(username)


@router.get(
    "/plan-history",
    tags=["info"],
    summary="The user's plan history",
    responses=user_not_exist_response_model,
)
async def plan_history(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
    id: Annotated[
        int | None,
        Query(description=("The plan identifier.")),
    ] = None,
) -> list[PlanHistory]:
    return manager.get_plan_history(username, id=id)


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
    "/latest-activity",
    tags=["info"],
    summary="The user's latest activity date",
    responses=user_not_exist_response_model,
)
async def latest_activity(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> datetime | None:
    return manager.get_latest_activity(username)


@router.get(
    "/latest-activities",
    tags=["info"],
    summary="The latest activity date of all the users",
)
async def latest_activities(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    from_date: Annotated[
        datetime | None,
        Query(
            description=(
                "The date range filter in `ISO 8601` format or `UNIX timestamp`."
                " If specified, only the activity dates beyond the specified"
                " date will be included."
            ),
        ),
    ] = None,
) -> dict[str, datetime]:
    return manager.get_latest_activities(from_date)


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
    "/has-active-plan-time",
    tags=["info"],
    summary="Whether the user has a plan with remained time",
    responses=user_not_exist_response_model,
)
async def has_active_plan_time(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.has_active_plan_time(username)


@router.get(
    "/has-active-plan-traffic",
    tags=["info"],
    summary="Whether the user has a plan with remained traffic",
    responses=user_not_exist_response_model,
)
async def has_active_plan_traffic(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> bool:
    return manager.has_active_plan_traffic(username)


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


@router.get(
    "/has-no-capacity",
    tags=["info"],
    summary="Whether the count of all the users is bigger than the capacity limit",
)
async def has_no_capacity(manager: Annotated[Manager, Depends(get_manager)]) -> bool:
    return manager.has_no_capacity()


@router.get(
    "/has-no-active-capacity",
    tags=["info"],
    summary=(
        "Whether the count of all the users that have"
        " an active plan is bigger than the capacity limit"
    ),
)
async def has_no_active_capacity(
    manager: Annotated[Manager, Depends(get_manager)],
) -> bool:
    return manager.has_no_active_capacity()
