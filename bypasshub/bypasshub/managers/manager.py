import asyncio
import logging
from threading import Lock
from contextlib import suppress
from typing import Self, Optional
from datetime import datetime, timedelta
from multiprocessing import current_process
from collections.abc import Iterable

from .xray import Xray
from .users import Users
from .state import State
from .openconnect import OpenConnect
from .. import errors
from ..utils import gather
from ..config import config
from ..types import Credentials, ManagerState
from ..constants import ServiceState, ManagerReason

Service = Xray | OpenConnect

manage_xray = config["main"]["manage_xray"]
manage_openconnect = config["main"]["manage_openconnect"]
logger = logging.getLogger(__name__)


class Manager(Users, State[ManagerState]):
    """The interface to manage the users on the services and database.

    Attributes:
        `skip_retry`:
            If `True` provided, only tries once to connect to the state
            synchronizer server and if failed, state synchronization with
            other ``Manager`` instances will be skipped when it's possible.
            Otherwise, ``errors.StateSynchronizerTimeout`` will be raised
            if could not establish a connection to the server after passed
            period of time.
            It's possible to retry to establish the connection with
            ``self.connect()`` method if the operation has failed.
    """

    __pid = None
    _async_locks = {}

    def __init__(self, *, skip_retry: bool | None = None) -> None:
        super().__init__()
        self._skip_retry = skip_retry
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

        if Manager.__pid != (pid := current_process().pid):
            Manager.__pid = pid
            if len(Manager._async_locks):
                # Parent processes forked this process.
                # Previous values should be ignored.
                Manager._async_locks.clear()

        State.__init__(self, __name__)
        super().connect(skip_retry=self._skip_retry)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exception) -> None:
        await self.close()

    def _load_state(self) -> None:
        super()._load_state()
        # Each individual user needs process and asynchronous locks.
        # Acquiring a process lock is blocking in asynchronous contexts.
        # Therefore, an asynchronous lock is also needed to prevent an
        # asynchronous context switch (on the same process) while a
        # process lock is needed to be acquired. Otherwise, without an
        # asynchronous lock, the acquired process lock will never release
        # and all the involved processes hang forever due to deadlocks.
        username = None
        with self._access_state():
            with self._global_lock:
                if not self._state:
                    self._state = self._dict()
                    self._state["reasons"] = self._dict()
                    self._state["users"] = self._dict()
                    self._add_user_state((username := self.usernames), synced=True)

        if not (async_locks := Manager._async_locks):
            for username in username or self.usernames:
                async_locks[username] = asyncio.Lock()

    def _add_user_state(
        self,
        usernames: Iterable[str],
        service_state: ServiceState | None = None,
        synced: bool | None = None,
        safe: bool | None = None,
    ) -> None:
        synced = bool(synced)
        users = self._state["users"]
        dict = self._dict
        lock = self._lock
        global_lock = self._global_lock
        async_locks = Manager._async_locks
        service_names = [service.NAME for service in self._services]
        for username in usernames:
            async_locks[username] = asyncio.Lock()
            has_active_plan = self.has_active_plan(username)
            _service_state = (
                service_state
                if service_state is not None
                else (ServiceState.ADDED if has_active_plan else ServiceState.DELETED)
            )

            try:
                # Preventing the other processes to replace the state
                if safe and not global_lock.acquire(blocking=False):
                    global_lock.acquire()
                    if username in users:
                        continue

                users[username] = dict(
                    {
                        "lock": lock(),
                        "synced": synced,
                        "has_active_plan": has_active_plan,
                        "services": dict(
                            {name: _service_state for name in service_names}
                        ),
                    }
                )
            finally:
                safe and global_lock.release()

    def _get_process_lock(
        self, username: str, silent: bool | None = None
    ) -> Optional[Lock]:
        with self._access_state(silent):
            users = self._state["users"]
            if username not in users:
                self._add_user_state(
                    (username,), service_state=ServiceState.UNKNOWN, safe=True
                )
            return users[username]["lock"]

    def _get_async_lock(self, username: str) -> asyncio.Lock:
        async_locks = Manager._async_locks
        try:
            return async_locks[username]
        except KeyError:
            lock = async_locks[username] = asyncio.Lock()
            return lock

    async def _add_user_by_service(
        self,
        service: Service,
        username: str,
        uuid: str,
        reason: ManagerReason | None = None,
        silent: bool | None = None,
        no_existence_log: bool | None = None,
    ) -> None:
        with self._access_state(silent):
            if (
                self._state["users"][username]["services"][service.NAME]
                == ServiceState.ADDED
            ):
                return

        modify_state = None
        try:
            await service.add_user(username, uuid)
        except errors.UserExistError:
            modify_state = True
            if not no_existence_log:
                logger.debug(
                    f"Tried to add existent user '{username}' to '{service.ALIAS}'"
                )
        else:
            modify_state = True
            if reason:
                logger.info(
                    f"Added user '{username}' to '{service.ALIAS}' due to {reason}"
                )
        finally:
            if modify_state:
                with self._access_state(silent):
                    self._state["users"][username]["services"][
                        service.NAME
                    ] = ServiceState.ADDED

    async def _delete_user_by_service(
        self,
        service: Service,
        username: str,
        reason: ManagerReason | None = None,
        silent: bool | None = None,
        no_existence_log: bool | None = None,
    ) -> None:
        with self._access_state(silent):
            if (
                self._state["users"][username]["services"][service.NAME]
                == ServiceState.DELETED
            ):
                return

        modify_state = None
        try:
            await service.delete_user(username)
        except errors.UserNotExistError:
            modify_state = True
            if not no_existence_log:
                logger.debug(
                    f"Tried to remove non-existent user '{username}'"
                    f" from '{service.ALIAS}'"
                )
        else:
            modify_state = True
            if reason:
                logger.info(
                    f"Removed user '{username}' from '{service.ALIAS}' due to {reason}"
                )
        finally:
            if modify_state:
                with self._access_state(silent):
                    self._state["users"][username]["services"][
                        service.NAME
                    ] = ServiceState.DELETED

    async def _add_user(
        self,
        username: str,
        uuid: str,
        reason: ManagerReason | None = None,
        silent: bool | None = None,
    ) -> None:
        process_lock = self._get_process_lock(username, silent)
        async_lock = process_lock and self._get_async_lock(username)

        try:
            if process_lock:
                await async_lock.acquire()
                with self._access_state(silent):
                    process_lock.acquire()

            if exceptions := (
                await gather(
                    [
                        self._add_user_by_service(
                            service, username, uuid, reason, silent
                        )
                        for service in self._services
                    ]
                )
            )[1]:
                raise ExceptionGroup(
                    errors.SynchronizationError.GROUP_MESSAGE, exceptions
                )

            with self._access_state(silent):
                user = self._state["users"][username]
                user["has_active_plan"] = True
                user["synced"] = True
                with suppress(KeyError):
                    del user["reason"]

        finally:
            if process_lock:
                with self._access_state(silent):
                    process_lock.release()
                async_lock.release()

    async def _delete_user(
        self,
        username: str,
        reason: ManagerReason | None = None,
        permanently: bool | None = None,
        silent: bool | None = None,
    ) -> None:
        process_lock = self._get_process_lock(username, silent)
        async_lock = process_lock and self._get_async_lock(username)

        try:
            if process_lock:
                await async_lock.acquire()
                with self._access_state(silent):
                    process_lock.acquire()

            if exceptions := (
                await gather(
                    [
                        self._delete_user_by_service(service, username, reason, silent)
                        for service in self._services
                    ]
                )
            )[1]:
                raise ExceptionGroup(
                    errors.SynchronizationError.GROUP_MESSAGE, exceptions
                )

            with self._access_state(silent):
                if permanently:
                    for dic in (
                        self._state["users"],
                        self._state["reasons"],
                        Manager._async_locks,
                    ):
                        with suppress(KeyError):
                            del dic[username]
                else:
                    user = self._state["users"][username]
                    user["has_active_plan"] = False
                    user["synced"] = True

        finally:
            if process_lock:
                with self._access_state(silent):
                    process_lock.release()
                async_lock.release()

    async def _sync(self) -> bool:
        synced = False
        current_usernames = self.usernames
        with self._access_state():
            users = self._state["users"]
            reasons = self._state["reasons"]

            for username in list(users.keys()):
                if username not in current_usernames:
                    # User is deleted
                    await self._delete_user(
                        username, ManagerReason.SYNCHRONIZATION, permanently=True
                    )
                    synced = True

            for username in current_usernames:
                method = args = None
                has_active_plan = self.has_active_plan(username)
                user = users.get(username, None)
                if user and user["synced"]:
                    # User is existed
                    had_active_plan = user["has_active_plan"]
                    if had_active_plan:
                        if not has_active_plan:
                            if not self.activate_reserved_plan(username):
                                method = self._delete_user
                                args = (ManagerReason.EXPIRED_PLAN,)
                            else:
                                synced = True
                    elif has_active_plan:
                        method = self._add_user
                        args = (
                            self.get_credentials(username)["uuid"],
                            reasons.get(username, ManagerReason.UPDATED_PLAN),
                        )
                    elif self.activate_reserved_plan(username):
                        reasons[username] = ManagerReason.RESERVED_PLAN
                        method = self._add_user
                        args = (
                            self.get_credentials(username)["uuid"],
                            ManagerReason.RESERVED_PLAN,
                        )
                else:
                    # User is added
                    if has_active_plan:
                        method = self._add_user
                        args = (
                            self.get_credentials(username)["uuid"],
                            reasons.get(username, ManagerReason.SYNCHRONIZATION),
                        )
                    elif self.activate_reserved_plan(username):
                        reasons[username] = ManagerReason.RESERVED_PLAN
                        method = self._add_user
                        args = (
                            self.get_credentials(username)["uuid"],
                            ManagerReason.RESERVED_PLAN,
                        )

                if method:
                    await method(username, *args)
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
            await self._add_user(**credentials, silent=True)
        except ExceptionGroup as _error:
            if not force:
                super().delete_user(username)
                with suppress(Exception):
                    await self._delete_user(username, permanently=True, silent=True)
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
            await self._delete_user(username, permanently=True, silent=True)
        except ExceptionGroup as _error:
            if not force:
                with suppress(Exception):
                    await self._add_user(**self.get_credentials(username), silent=True)
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
                    await self._delete_user(
                        username, ManagerReason.EXPIRED_PLAN, silent=True
                    )
                    reflected = True
            elif has_active_plan:
                await self._add_user(
                    *self.get_credentials(username).values(),
                    ManagerReason.UPDATED_PLAN,
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
        By running this, users' reserved plans also get activated if the
        users do not have an active plan.

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
