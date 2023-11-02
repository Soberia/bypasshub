from typing import Any
from collections.abc import Sequence

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from .types import SerializedError
from .constants import XrayService, OpenConnectService

SQLITE_CONSTRAINT_PRIMARYKEY = 1555
SQLITE_CONSTRAINT_UNIQUE = 2067


class BaseError(Exception):
    """The base exception that can be inherited by the other exceptions.

    Attributes:
        `message`:
            The error message.
        `code`:
            The error code.
        `http_code`:
            The HTTP error code that would be used for the RESTful API.
        `cause`:
            The exception that will be stored as `__cause__` attribute.
            `ValueError` will be raised if value is not an exception.
        `payload`:
            The serializable value that could be stored for any use case.
    """

    def __init__(
        self,
        message: str,
        code: int,
        http_code: int,
        *,
        cause: BaseException | None = None,
        payload: Any = None,
    ) -> None:
        self.message = message
        self.code = code
        self.http_code = http_code
        self.payload = payload
        if cause:
            if not isinstance(cause, Exception):
                raise ValueError(
                    "The 'cause' parameter must be instance of the 'Exception' class"
                )
            self.__cause__ = cause

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        if cause := self.__cause__:
            return "".join(
                [
                    f"{self.message} due to:\n",
                    *(
                        f"\t\t\t- {exception}\n"
                        for exception in (
                            cause.exceptions
                            if isinstance(cause, ExceptionGroup)
                            else (cause,)
                        )
                    ),
                ]
            )
        return self.message

    def _serialize_exception(
        self, exception: Exception, _group: str | None = None
    ) -> SerializedError | list[SerializedError]:
        if isinstance(exception, ExceptionGroup):
            group = exception.message
            errors = [
                self._serialize_exception(exec, group) for exec in exception.exceptions
            ]
            return errors[0] if len(errors) == 1 else errors

        serialized = {"type": exception.__class__.__name__, "message": str(exception)}
        if _group:
            serialized["group"] = _group
        if isinstance(exception, BaseError):
            serialized["code"] = exception.code
            if exception.__cause__:
                cause = self._serialize_exception(exception.__cause__)
                serialized["cause"] = cause if type(cause) is list else [cause]
            if exception.payload is not None:
                serialized["payload"] = exception.payload

        return serialized

    def serialize(self) -> list[SerializedError]:
        """Returns the serializable version of the exception."""
        serialized = self._serialize_exception(self)
        return serialized if type(serialized) is list else [serialized]

    @staticmethod
    def create_exception_group(
        message: str, exceptions: Sequence[Exception] | Exception | None
    ) -> ExceptionGroup | None:
        """Wraps the given exceptions inside of an `ExceptionGroup`"""
        if exceptions:
            if isinstance(exceptions, Exception):
                if isinstance(exceptions, ExceptionGroup):
                    return exceptions
                exceptions = (exceptions,)
            return ExceptionGroup(message, exceptions)


class UnexpectedError(BaseError):
    """Unexpected error happened."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Unexpected error happened", 0, HTTP_500_INTERNAL_SERVER_ERROR, **kwargs
        )

    def serialize(self) -> list[SerializedError]:
        if self.__cause__:
            for exception in (
                self.__cause__.exceptions
                if isinstance(self.__cause__, ExceptionGroup)
                else [self.__cause__]
            ):
                if not isinstance(exception, BaseError):
                    return super().serialize()

            # All the exceptions are subclass of the ``BaseError``.
            # Therefore, using them directly instead of wrapping
            # them inside of ``UnexpectedError``.
            serialized = self._serialize_exception(self.__cause__)
            return serialized if type(serialized) is list else [serialized]

        return super().serialize()


class InvalidUsernameError(BaseError):
    """Username is not valid."""

    def __init__(self, username: str = "", **kwargs) -> None:
        super().__init__(
            f"Username {username and f''''{username}' '''}is not valid",
            1,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class InvalidCredentialsError(BaseError):
    """User credentials is not valid."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            f"User credentials is not valid",
            2,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class UserExistError(BaseError):
    """User already exists."""

    def __init__(self, username: str = "", **kwargs) -> None:
        super().__init__(
            f"User {username and f''''{username}' '''}already exists",
            3,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class UserNotExistError(BaseError):
    """User does not exist."""

    def __init__(self, username: str = "", **kwargs) -> None:
        super().__init__(
            f"User {username and f''''{username}' '''}does not exist",
            4,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class UUIDOverlapError(BaseError):
    """Cannot create the user due to overlapped UUIDs."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "Cannot create the user due to overlapped UUIDs",
            5,
            HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs,
        )


class UsersCapacityError(BaseError):
    """Cannot create the user due to capacity limit."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            f"Cannot create the user due to capacity limit",
            6,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class ActiveUsersCapacityError(UsersCapacityError):
    """Cannot create the user due to capacity limit."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.code = 7


class NoTrafficLimitError(BaseError):
    """Cannot add extra traffic for the user with unlimited traffic plan."""

    def __init__(self, username: str = "", **kwargs) -> None:
        super().__init__(
            f"Cannot add extra traffic {username and f'''for the user '{username}' '''}"
            "when plan has no traffic limit",
            9,
            HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class XrayTimeoutError(BaseError):
    """Failed to communicate with `Xray-core` service."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            f"Failed to communicate with '{XrayService.ALIAS}' proxy server",
            10,
            HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs,
        )


class OpenConnectTimeoutError(BaseError):
    """Failed to communicate with `OpenConnect` service."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            f"Failed to communicate with '{OpenConnectService.ALIAS}' VPN server",
            11,
            HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs,
        )


class SynchronizationError(BaseError):
    """Failed to reflect the changes to the related services."""

    GROUP_MESSAGE = "User Synchronization Task Group"

    def __init__(
        self, *, cause: Sequence[Exception] | Exception | None = None, **kwargs
    ) -> None:
        super().__init__(
            "Failed to reflect the changes to the related services",
            12,
            HTTP_500_INTERNAL_SERVER_ERROR,
            cause=self.create_exception_group(self.GROUP_MESSAGE, cause),
            **kwargs,
        )
