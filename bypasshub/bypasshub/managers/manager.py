import logging
from typing import Self
from enum import StrEnum
from contextlib import suppress
from datetime import datetime, timedelta

from .xray import Xray
from .users import Users
from .openconnect import OpenConnect
from .. import errors
from ..utils import gather
from ..config import config
from ..types import Credentials

Service = Xray | OpenConnect

manage_xray = config["main"]["manage_xray"]
manage_openconnect = config["main"]["manage_openconnect"]
logger = logging.getLogger(__name__)


class Reason(StrEnum):
    UPDATED_PLAN = "updated plan"
    EXPIRED_PLAN = "expired plan"
    SYNCHRONIZATION = "database synchronization"
    ZOMBIE_USER = "user doesn't exist on database"


class Manager(Users):
    """The interface to manage the users on the services and database."""

    def __init__(self) -> None:
        super().__init__()
        self._xray = None
        self._openconnect = None
        self._services: list[Service] = []
        if manage_xray:
            self._xray = Xray()
            self._services.append(self._xray)
        if manage_openconnect:
            self._openconnect = OpenConnect()
            self._services.append(self._openconnect)

        if not self._services:
            raise RuntimeError("No service is enabled for managing")

        self._users = {
            username: self.has_active_plan(username) for username in self.usernames
        }

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exception) -> None:
        await self.close()

    async def _add_user_by_service(
        self,
        service: Service,
        username: str,
        uuid: str,
        reason: Reason | None = None,
        silent: bool | None = None,
    ) -> None:
        try:
            await service.add_user(username, uuid)
        except errors.UserExistError:
            if not silent:
                logger.debug(
                    f"Tried to add existent user '{username}' to '{service.ALIAS}'"
                )
        else:
            if reason:
                logger.info(
                    f"Added user '{username}' to '{service.ALIAS}' due to {reason}"
                )

    async def _delete_user_by_service(
        self,
        service: Service,
        username: str,
        reason: Reason | None = None,
        silent: bool | None = None,
    ) -> None:
        try:
            await service.delete_user(username)
        except errors.UserNotExistError:
            if not silent:
                logger.debug(
                    f"Tried to remove non-existent user '{username}'"
                    f" from '{service.ALIAS}'"
                )
        else:
            if reason:
                logger.info(
                    f"Removed user '{username}' from '{service.ALIAS}' due to {reason}"
                )

    async def _add_user(
        self,
        username: str,
        uuid: str,
        reason: Reason | None = None,
        silent: bool | None = None,
    ) -> None:
        if exceptions := (
            await gather(
                [
                    self._add_user_by_service(service, username, uuid, reason, silent)
                    for service in self._services
                ]
            )
        )[1]:
            raise ExceptionGroup(errors.SynchronizationError.GROUP_MESSAGE, exceptions)

    async def _delete_user(
        self, username: str, reason: Reason | None = None, silent: bool | None = None
    ) -> None:
        if exceptions := (
            await gather(
                [
                    self._delete_user_by_service(service, username, reason, silent)
                    for service in self._services
                ]
            )
        )[1]:
            raise ExceptionGroup(errors.SynchronizationError.GROUP_MESSAGE, exceptions)

    async def _sync(self, *, silent: bool | None = None) -> bool:
        synced = False
        current_usernames = self.usernames

        for username in list(self._users):
            if username not in current_usernames:
                # User is deleted
                await self._delete_user(username, Reason.SYNCHRONIZATION, silent)
                del self._users[username]
                synced = True

        for username in current_usernames:
            method = args = None
            has_active_plan = self.has_active_plan(username)
            try:
                # User is existed
                had_active_plan = self._users[username]
                if had_active_plan:
                    if not has_active_plan:
                        method = self._delete_user
                        args = (Reason.EXPIRED_PLAN,)
                elif has_active_plan:
                    method = self._add_user
                    args = (self.get_credentials(username)["uuid"], Reason.UPDATED_PLAN)
            except KeyError:
                # User is added
                if has_active_plan:
                    method = self._add_user
                    args = (
                        self.get_credentials(username)["uuid"],
                        Reason.SYNCHRONIZATION,
                    )

            if method:
                await method(username, *args, silent)
                self._users[username] = has_active_plan
                synced = True

        if synced:
            self.generate_list()

        return synced

    async def add_user(
        self, username: str, *, force: bool | None = None
    ) -> Credentials:
        """Adds the user to the services and database.

        Args:
            `force`:
                Force the creation of the user. If omitted or `False` provided,
                the created user in the database would only be kept if user also
                successfully added to the services. Otherwise, if `True` provided,
                and it's not possible to add the user to the services for example
                due to a timeout error, the user would be added to the database
                anyway. However, ``errors.SynchronizationError`` will be raised
                to indicate the cause of the synchronization problem with services.

        Returns:
            The credentials of created user that can be used
            to connect to the services.

        Raises:
            `ExceptionGroup`:
                When failed to delete the user from the services.
                This will only be raised if the `force` parameter is not `True`.
            ``errors.SynchronizationError``:
                When failed to add the user to the services.
                This will only be raised if the `force` parameter sets to `True`.
                The created user's credentials will be stored in the `payload`
                attribute.
        """
        credentials = super().add_user(username)
        username = credentials["username"]
        error = None
        try:
            await self._add_user(**credentials)
        except ExceptionGroup as _error:
            if not force:
                super().delete_user(username)
                with suppress(Exception):
                    await self._delete_user(username)
                logger.error(f"Failed to create user '{username}'")
                raise _error
            error = errors.SynchronizationError(
                f"Failed to add user '{username}' to the services",
                cause=_error,
                payload=credentials,
            )
            logger.warning(repr(error))

        logger.info(f"User '{username}' is created")
        if error:
            raise error
        return credentials

    async def delete_user(self, username: str, *, force: bool | None = None) -> None:
        """Deletes the user from the services and database.

        Args:
            `force`:
                Force the deleting of the user. If omitted or `False` provided,
                the user would only be deleted from the database if user was also
                successfully deleted from the services. Otherwise, if `True` provided,
                and it's not possible to delete the user from the services for example
                due to a timeout error, the user would be deleted from the database
                anyway. However, ``errors.SynchronizationError`` will be raised
                to indicate the cause of the synchronization problem with services.

        Raises:
            `ExceptionGroup`:
                When failed to delete the user from the services.
                This will only be raised if the `force` parameter is not `True`.
            ``errors.SynchronizationError``:
                When failed to delete the user from the services.
                This will only be raised if the `force` parameter sets to `True`.
        """
        username = self.validate_username(username)
        if not self._is_exist(username):
            raise errors.UserNotExistError(username)

        error = None
        try:
            await self._delete_user(username)
        except ExceptionGroup as _error:
            if not force:
                with suppress(Exception):
                    await self._add_user(**self.get_credentials(username))
                logger.error(f"Failed to delete user '{username}'")
                raise _error
            error = errors.SynchronizationError(
                f"Failed to delete user '{username}' from the services", cause=_error
            )
            logger.warning(repr(error))

        super().delete_user(username)
        logger.info(f"User '{username}' is deleted")
        if error:
            raise error

    async def update_plan(
        self,
        username: str,
        *,
        id: int | None = None,
        start_date: datetime | str | int | float | None = None,
        duration: timedelta | int | None = None,
        traffic: int | None = None,
        extra_traffic: int | None = None,
        reset_extra_traffic: bool | None = None,
        preserve_traffic_usage: bool | None = None,
    ) -> None:
        """
        Updates the user's plan on the database
        and reflects the changes to the services.

        Args:
            `id`:
                The identifier related to this plan update that would be
                stored in the database plan history table.
            `start_date`:
                The plan start date in ISO 8601 format if provided value is `str`
                or UNIX timestamp if provided value is a number.
                If omitted, no time restriction will be applied.
            `duration`:
                The plan duration in seconds.
            `traffic`:
                The plan traffic limit in bytes.
                If omitted, no traffic restriction will be applied.
            `extra_traffic`:
                The plan extra traffic limit in bytes.
                If user's plan traffic limit is reached, this value will
                be consumed instead for managing the user's traffic usage.
            `reset_extra_traffic`:
                If `True` provided, the `extra_traffic` parameter value will
                be ignored and extra traffic limit will be reset.
            `preserve_traffic_usage`:
                If `True` provided, recorded traffic usage will not reset
                and the value from the previous plan will be preserved.

        Raises:
            ``errors.SynchronizationError``:
                When failed to reflect the plan updates to the services.
        """
        username = self.validate_username(username)
        had_active_plan = self.has_active_plan(username)
        set_extra_traffic = extra_traffic is not None or reset_extra_traffic is not None
        if not (
            set_extra_traffic
            and all(
                parameter is None
                for parameter in (start_date, duration, traffic, preserve_traffic_usage)
            )
        ):
            self.set_plan(
                username,
                id=id,
                start_date=start_date,
                duration=duration,
                traffic=traffic,
                preserve_traffic_usage=preserve_traffic_usage,
            )
        if set_extra_traffic:
            self.set_plan_extra_traffic(
                username,
                id=id,
                extra_traffic=(None if reset_extra_traffic is True else extra_traffic),
            )
        has_active_plan = self.has_active_plan(username)

        error = reflected = None
        try:
            if had_active_plan:
                if not has_active_plan:
                    await self._delete_user(username, Reason.EXPIRED_PLAN, silent=True)
                    reflected = True
            elif has_active_plan:
                await self._add_user(
                    *self.get_credentials(username).values(),
                    Reason.UPDATED_PLAN,
                    silent=True,
                )
                reflected = True
        except Exception as _error:
            error = errors.SynchronizationError(
                f"Failed to reflect plan update to the services for user '{username}'",
                cause=_error,
            )
            logger.warning(repr(error))
            raise error
        finally:
            logger.info(
                "Plan is updated for user '{}'{}".format(
                    username,
                    (
                        " and currently no changes are required"
                        " to be reflected to the services"
                    )
                    if not reflected and not error
                    else "",
                )
            )

    async def sync(self) -> bool:
        """Synchronizes the services with the database.

        This method should be called when ``errors.SynchronizationError``
        exception is raised during calling other methods of this class
        or when the database is modified manually or by other external
        processes while the main process is up and running.

        Returns:
            Whether the synchronization is performed.
            If `False` returned, that means services are already in sync.

        Raises:
            ``errors.SynchronizationError``:
                When failed to reflect the database changes to the services.
        """
        try:
            return await self._sync()
        except Exception as error:
            raise errors.SynchronizationError(
                "Failed to reflect the database changes to the services", cause=error
            )

    async def close(self) -> None:
        """Closes the connections to the services and database."""
        for service in self._services:
            if hasattr(service, "close"):
                await service.close()

        super().close()
