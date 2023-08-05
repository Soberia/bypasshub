import asyncio
import logging
from typing import Literal
from collections.abc import Coroutine

from . import errors
from .utils import gather
from .config import config
from .managers import Manager, Xray
from .managers.manager import Reason, Service

TASK_NAME_PREFIX = "monitor"
TASK_GROUP_MESSAGE = "User Monitor Task Group"

monitor_interval = config["main"]["monitor_interval"]
monitor_passive_steps = config["main"]["monitor_passive_steps"]
monitor_zombies = config["main"]["monitor_zombies"]
logger = logging.getLogger(__name__)


class Monitor(Manager):
    """
    The monitor procedure that manages the services by tracking the database
    and users traffic consumption.

    Attributes:
        `interval`:
            The interval in seconds to wait for tracking users traffic usage
            and remove them from the services if they do not have an active plan.
            `ValueError` will be raised if value is not a positive number.
            The default value is equal to `monitor_interval` property of the
            configuration file.
        `steps`:
            The services synchronization with the database interval.
            This interval is calculated by multiplying the passed value to
            the `monitor_interval` parameter.
            The default value is equal to `monitor_passive_steps` property
            of the configuration file.
            If not a positive integer is provided, the synchronization will
            be disabled.
    """

    def __init__(
        self,
        interval: int | float = monitor_interval,
        steps: int = monitor_passive_steps,
    ) -> None:
        super().__init__()
        self.interval = interval
        self.steps = steps
        if self.interval <= 0:
            raise ValueError("The 'interval' parameter should be grater than zero")

        self._sync_enabled = self.steps > 0
        if not self._sync_enabled:
            logger.info("Services and database synchronization procedure is disabled")

        self._task = None
        self._idle = None
        self._counted_steps = 0

    async def _passive_monitor(self) -> None:
        """Periodically synchronizes the services with the database."""
        self._counted_steps += 1
        if self.steps > 1 and self._counted_steps < self.steps:
            return

        await self._sync(silent=True)
        self._counted_steps = 0

    async def _active_monitor(self, *, service: Service) -> None:
        """
        Updates the traffic usage for the users that are active and connected
        to the specified service in the current time and removes those ones
        that not have an active plan from the service.
        """
        # `Xray-core` still reports traffic usage for the deleted users
        silent_delete = isinstance(service, Xray)

        for username, traffic in (await service.users_traffic_usage()).items():
            try:
                plan = self.get_plan(username)
            except errors.UserNotExistError:
                if not silent_delete:
                    logger.warning(
                        f"User '{username}' is active on '{service.ALIAS}'"
                        " but does not exist on the database"
                    )
                if monitor_zombies:
                    await self._delete_user_by_service(
                        service,
                        username,
                        Reason.ZOMBIE_USER,
                        silent_delete,
                    )

                continue

            uplink = traffic["uplink"]
            downlink = traffic["downlink"]
            if (session_traffic_usage := uplink + downlink) > 0:
                added_traffic_usage = added_extra_traffic_usage = 0
                if not self._is_unlimited_traffic_plan(plan):
                    plan_traffic = plan["plan_traffic"]
                    previous_traffic_usage = plan["plan_traffic_usage"]
                    added_traffic_usage = session_traffic_usage
                    plan["plan_traffic_usage"] += added_traffic_usage
                    if (
                        plan["plan_extra_traffic"]
                        and plan["plan_traffic_usage"] > plan_traffic
                    ):
                        added_traffic_usage = plan_traffic - previous_traffic_usage
                        added_extra_traffic_usage = (
                            session_traffic_usage - added_traffic_usage
                        )
                        plan["plan_traffic_usage"] = plan_traffic
                        plan["plan_extra_traffic_usage"] += added_extra_traffic_usage

                # The database should be updated before asynchronous context switch
                self._update_traffic(
                    username,
                    added_traffic_usage,
                    added_extra_traffic_usage,
                    uplink,
                    downlink,
                )

            if not self.has_active_plan(username, plan=plan):
                await self._delete_user_by_service(
                    service,
                    username,
                    Reason.EXPIRED_PLAN,
                    silent_delete,
                )

    async def _monitor(
        self, tasks: list[tuple[Coroutine, dict[Literal["service"], Service], str]]
    ) -> None:
        while True:
            if not self._task:
                return

            self._idle = True
            await asyncio.sleep(self.interval)
            self._idle = False

            try:
                try:
                    if exceptions := (
                        await gather(
                            [
                                asyncio.create_task(task(**kwargs), name=name)
                                for task, kwargs, name in tasks
                            ],
                        )
                    )[1]:
                        # Merging all the exceptions
                        _exceptions = []
                        for exception in exceptions:
                            if isinstance(exception, ExceptionGroup):
                                _exceptions.extend(exception.exceptions)
                            else:
                                _exceptions.append(exception)
                        raise ExceptionGroup(TASK_GROUP_MESSAGE, _exceptions)
                except* (
                    errors.XrayTimeoutError,
                    errors.OpenConnectTimeoutError,
                ) as error:
                    for exception in error.exceptions:
                        logger.warning(exception)
            except ExceptionGroup as error:
                logger.exception(error)

    def start(self) -> asyncio.Task:
        """Starts the monitor procedure.

        Returns:
            The related AsyncIO Task that can be awaited on.

        Raises:
            `RuntimeError`:
                When called while the monitor procedure is already running
                or after calling the ``self.stop()`` method.
        """
        if self._task is not None:
            raise RuntimeError("The monitor procedure is already running")
        elif self._closed:
            raise RuntimeError("The monitor procedure was stopped")

        tasks = [
            (
                self._active_monitor,
                {"service": service},
                f"{TASK_NAME_PREFIX}_active_{service.NAME}",
            )
            for service in self._services
        ]
        if self._sync_enabled:
            tasks.append((self._passive_monitor, {}, f"{TASK_NAME_PREFIX}_passive"))

        self._task = asyncio.create_task(self._monitor(tasks), name=TASK_NAME_PREFIX)
        logger.info("The monitor procedure is started")
        return self._task

    async def stop(self, force: bool = False) -> None:
        """Stops the monitor procedure.

        Args:
            `force`:
                If `True` provided, stops the procedure immediately.
                Otherwise, waits for the current monitor iteration
                to be finished and then stops the procedure.
        """
        if _task := self._task:
            self._task = None
            if self._idle or force:
                if not _task.cancelled():
                    _task.cancel()
            else:
                await _task

            self._idle = None
            self._counted_steps = 0

            await self.close()
            logger.info("The monitor procedure is stopped")
