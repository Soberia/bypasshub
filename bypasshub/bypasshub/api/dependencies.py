from typing import Annotated

from fastapi import Request, Query

from ..managers import Manager
from ..managers.users import (
    username_pattern,
    USERNAME_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
)


def get_manager(request: Request) -> Manager:
    """Returns the manager."""
    return request.app.state.manager


def validate_username(
    username: Annotated[
        str,
        Query(
            description="The user's username",
            min_length=USERNAME_MIN_LENGTH,
            max_length=USERNAME_MAX_LENGTH,
            pattern=username_pattern.pattern,
        ),
    ],
) -> str:
    """Returns the lowercased version of the passed value after the validation."""
    return username.lower()
