from typing import Annotated

from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import PlainTextResponse
from starlette.status import HTTP_400_BAD_REQUEST


from .user import user_not_exist_example
from ..utils import http_not_found
from ..dependencies import get_manager, validate_username
from ...managers import Manager
from ...types import Credentials, HTTPSerializedError
from ...errors import InvalidUsernameError, UserNotExistError, InvalidCredentialsError


router = APIRouter()


@router.get(
    "/subscription",
    tags=["subscription"],
    summary="Generates 'Xray-core' config URLs for the user",
    response_model=str,
    responses={
        HTTP_400_BAD_REQUEST: {
            "model": HTTPSerializedError,
            "content": {
                "application/json": {
                    "examples": {
                        **user_not_exist_example,
                        "user credentials is not valid": {
                            "value": {
                                "details": [InvalidCredentialsError().serialize()]
                            }
                        },
                    }
                }
            },
        },
    },
)
async def xray_subscription(
    request: Request,
    manager: Annotated[Manager, Depends(get_manager)],
    *,
    username: Annotated[str, Depends(validate_username)],
    uuid: Annotated[str, Query(description="The user's UUID")],
) -> PlainTextResponse:
    try:
        if manager.validate_credentials(Credentials(username=username, uuid=uuid)):
            return PlainTextResponse(manager._xray.generate_subscription(uuid))
    except InvalidUsernameError:
        pass

    # Returning the error for the API endpoint
    if request.url.path != "/subscription":
        if not manager.is_exist(username):
            raise UserNotExistError(username)
        raise InvalidCredentialsError()

    return await http_not_found()
