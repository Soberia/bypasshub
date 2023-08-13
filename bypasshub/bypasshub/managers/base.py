from abc import ABC, abstractmethod

from ..types import Traffic


class BaseService(ABC):
    @classmethod
    @property
    @abstractmethod
    def NAME(cls) -> str:
        """The service's name."""
        raise NotImplementedError()

    @classmethod
    @property
    @abstractmethod
    def ALIAS(cls) -> str:
        """The service's alias."""
        raise NotImplementedError()

    @abstractmethod
    async def add_user(self, username: str, uuid: str) -> None:
        """Adds the user to the current service session.

        Raises:
            ``errors.UserExistError``:
                When the specified user already exists.
        """
        raise NotImplementedError()

    @abstractmethod
    async def delete_user(self, username: str) -> None:
        """Deletes the user from the current service session.

        Raises:
            ``errors.UserNotExistError``:
                When the specified user does not exist.
        """
        raise NotImplementedError()

    @abstractmethod
    async def user_traffic_usage(self, username: str, reset: bool) -> Traffic:
        """Returns the user's traffic usage since start of the current service session.

        Args:
            `reset`:
                If `True` provided, traffic usage is calculated from
                the last time this method was called. Otherwise, the
                returned traffic usage is the sum of the previous value.
        """
        raise NotImplementedError()

    @abstractmethod
    async def users_traffic_usage(self, reset: bool) -> dict[str, Traffic]:
        """Returns users traffic usage since start of the current service session.

        The keys of the returned dictionary, is representing the user's
        username and the value is the traffic usage for that user.

        Args:
            `reset`:
                If `True` provided, traffic usage is calculated from
                the last time this method was called. Otherwise, the
                returned traffic usage is the sum of the previous value.
        """
        raise NotImplementedError()
