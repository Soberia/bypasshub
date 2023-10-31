from uuid import uuid4
from typing import Annotated
from datetime import timedelta

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import PydanticCustomError, InitErrorDetails
from fastapi import APIRouter, Depends, Query, Body
from fastapi.exceptions import RequestValidationError
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from ..dependencies import get_manager, validate_username
from ... import errors
from ...managers import Manager
from ...utils import current_time
from ...types import HTTPSerializedError, Credentials

router = APIRouter(prefix="/user")

service_timeout_example = {
    "failed to communicate with `Xray-core` service": {
        "value": {"details": [errors.XrayTimeoutError().serialize()]},
    },
    "failed to communicate with `OpenConnect` service": {
        "value": {"details": [errors.OpenConnectTimeoutError().serialize()]},
    },
}

user_not_exist_example = {
    "user doesn't exist": {
        "value": {"details": [errors.UserNotExistError("john_doe").serialize()]}
    }
}

user_not_exist_response_model = {
    HTTP_400_BAD_REQUEST: {
        "model": HTTPSerializedError,
        "content": {"application/json": {"examples": user_not_exist_example}},
    },
}


class PlanRequest(BaseModel):
    plan_start_date: Annotated[
        str | int | None,
        Field(
            alias="start-date",
            description=(
                "The plan start date in `ISO 8601` format or `UNIX timestamp`."
                " If not specified, no time restriction will be applied."
            ),
        ),
    ] = None
    plan_duration: Annotated[
        int | None, Field(alias="duration", description="The plan duration in seconds.")
    ] = None
    plan_traffic: Annotated[
        int | None,
        Field(
            alias="traffic",
            description=(
                "The plan traffic limit in bytes."
                " If not specified, no traffic restriction will be applied."
            ),
        ),
    ] = None
    plan_extra_traffic: Annotated[
        int | None,
        Field(
            alias="extra-traffic",
            description=(
                "The plan extra traffic limit in bytes."
                " If user's plan traffic limit is reached,"
                " this value will be consumed for managing the user's traffic usage."
            ),
        ),
    ] = None


@router.get(
    "/add",
    tags=["user"],
    summary="Adds a user",
    response_description="The credentials of created user",
    responses={
        HTTP_200_OK: {
            "model": Credentials,
            "content": {
                "application/json": {
                    "examples": {
                        "user is added": {
                            "value": Credentials(username="john_doe", uuid=str(uuid4()))
                        }
                    }
                }
            },
        },
        HTTP_400_BAD_REQUEST: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        "user already exists": {
                            "value": {
                                "details": [
                                    errors.UserExistError("john_doe").serialize()
                                ]
                            }
                        },
                        "users capacity is full": {
                            "value": {
                                "details": [errors.UsersCapacityError().serialize()]
                            }
                        },
                        "users with active plan capacity is full": {
                            "value": {
                                "details": [
                                    errors.ActiveUsersCapacityError().serialize()
                                ]
                            }
                        },
                    }
                }
            },
        },
        HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        **service_timeout_example,
                        "user is added by force": {
                            "value": {
                                "details": [
                                    errors.SynchronizationError(
                                        cause=errors.XrayTimeoutError(),
                                        payload=Credentials(
                                            username="john_doe", uuid=str(uuid4())
                                        ),
                                    ).serialize()
                                ]
                            },
                        },
                        "failed to generate an unique UUID": {
                            "value": {
                                "details": [errors.UUIDOverlapError().serialize()]
                            }
                        },
                    }
                }
            },
        },
    },
)
async def add(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
    force: Annotated[
        bool,
        Query(
            description=(
                "Force the creation of the user. If not specified or `false` provided,"
                " the created user in the database would only be kept if user also"
                " successfully added to the services. Otherwise, if `true` provided,"
                " and it's not possible to add the user to the services for example"
                " due to a timeout error, the user would be added to the database"
                " anyway. However, HTTP 500 error will be returned to indicate the"
                " cause of the synchronization problem with services."
                " The created user's credentials will be stored in the `payload`"
                " property of returned `HTTPSerializedError` response error."
            )
        ),
    ] = None,
) -> Credentials:
    return await manager.add_user(username, force=force)


@router.delete(
    "/delete",
    tags=["user"],
    summary="Deletes a user",
    responses={
        **user_not_exist_response_model,
        HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        **service_timeout_example,
                        "user is deleted by force": {
                            "value": {
                                "details": [
                                    errors.SynchronizationError(
                                        cause=errors.XrayTimeoutError()
                                    ).serialize()
                                ]
                            },
                        },
                    }
                }
            },
        },
    },
)
async def delete(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
    force: Annotated[
        bool,
        Query(
            description=(
                "Force the deleting of the user. If not specified or `false` provided,"
                " the user would only be deleted from the database if user was also"
                " successfully deleted from the services. Otherwise, if `true` provided,"
                " and it's not possible to delete the user from the services for example"
                " due to a timeout error, the user would be deleted from the database"
                " anyway. However, HTTP 500 error will be returned to indicate the"
                " cause of the synchronization problem with services."
            )
        ),
    ] = None,
) -> "None":
    await manager.delete_user(username, force=force)


@router.patch(
    "/update-plan",
    tags=["user"],
    summary="Updates the user's plan",
    responses={
        HTTP_400_BAD_REQUEST: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        **user_not_exist_example,
                        "set extra traffic limit while plan has no traffic limit": {
                            "value": {
                                "details": [errors.NoTrafficLimitError().serialize()]
                            },
                        },
                    }
                }
            },
        },
        HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        "failed to reflect the plan updates to the services": {
                            "value": {
                                "details": [
                                    errors.SynchronizationError(
                                        cause=errors.XrayTimeoutError()
                                    ).serialize()
                                ]
                            },
                        },
                    }
                }
            },
        },
    },
)
async def update_plan(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
    id: Annotated[
        int | None,
        Query(
            description=(
                "The identifier related to this plan update that would be"
                " stored in the database plan history table."
            )
        ),
    ] = None,
    plan: Annotated[
        PlanRequest,
        Body(
            openapi_examples={
                "unlimited traffic for one month": {
                    "value": {
                        "start-date": current_time().isoformat(),
                        "duration": int(timedelta(days=30).total_seconds()),
                    }
                },
                "10GB traffic for one month": {
                    "value": {
                        "start-date": current_time().isoformat(),
                        "duration": int(timedelta(days=30).total_seconds()),
                        "traffic": 1e10,
                    }
                },
                "10GB traffic for unlimited time": {"value": {"traffic": 1e10}},
                "add 1GB extra traffic": {"value": {"extra-traffic": 1e9}},
                "unlimited traffic and time": {"value": {}},
            }
        ),
    ],
    reset_extra_traffic: Annotated[
        bool,
        Query(
            alias="reset-extra-traffic", description="Reset the extra traffic limit."
        ),
    ] = None,
    preserve_traffic_usage: Annotated[
        bool,
        Query(
            alias="preserve-traffic-usage",
            description="Do not reset the recorded traffic usage from the previous plan.",
        ),
    ] = None,
) -> "None":
    try:
        await manager.update_plan(
            username,
            id=id,
            start_date=plan.plan_start_date,
            duration=plan.plan_duration,
            traffic=plan.plan_traffic,
            extra_traffic=plan.plan_extra_traffic,
            reset_extra_traffic=reset_extra_traffic,
            preserve_traffic_usage=preserve_traffic_usage,
        )
    except ValueError as error:
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value-error", message := str(error).replace("_", "-")
                            ),
                            loc=("body", message.split()[0].replace("'", "")),
                        )
                    ],
                )
            ).errors()
        )


@router.put(
    "/reset-total-traffic",
    tags=["user"],
    summary="Resets the user's total traffic consumption",
    responses=user_not_exist_response_model,
)
async def reset_total_traffic(
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
) -> "None":
    manager.reset_total_traffic(username)
