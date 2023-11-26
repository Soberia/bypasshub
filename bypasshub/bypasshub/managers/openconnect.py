import asyncio
import logging
from typing import Any
from pathlib import Path
from contextlib import suppress

import orjson

from .base import BaseService
from .. import errors
from ..types import Traffic
from ..config import config
from ..constants import OpenConnectService

timeout = config["main"]["service_timeout"]
broker_socket_path = Path(config["main"]["occtl_broker_socket_path"])
logger = logging.getLogger(__name__)


class OpenConnect(BaseService):
    """
    The `OpenConnect` VPN server service.

    Attributes:
        `timeout`:
            The time in seconds to wait for the communications to the
            service to be finished. After that, ``errors.OpenConnectTimeoutError``
            will be raised.
            `ValueError` will be raised if value is not a positive number.
            The default value is equal to `service_timeout` property of the
            configuration file.
    """

    NAME = OpenConnectService.NAME
    ALIAS = OpenConnectService.ALIAS

    def __init__(self, timeout: int | float = timeout) -> None:
        self.timeout = timeout
        if self.timeout <= 0:
            raise ValueError("The 'timeout' parameter should be greater than zero")

        self._last_boot = None
        self._traffic_loaded = None
        self._traffic = {}

    async def _exec(self, command: str) -> Any:
        """Communicates with the `OpenConnect` message broker script."""
        try:
            async with asyncio.Timeout(
                asyncio.get_running_loop().time() + self.timeout
            ):
                reader = writer = None
                while True:
                    try:
                        reader, writer = await asyncio.open_unix_connection(
                            broker_socket_path
                        )
                    except (FileNotFoundError, ConnectionRefusedError, BlockingIOError):
                        await asyncio.sleep(0.1)
                    else:
                        break

                writer.write(command.encode())
                writer.write_eof()

                try:
                    await writer.drain()
                except ConnectionResetError:
                    raise errors.OpenConnectTimeoutError()
                else:
                    # The first byte is the exit code
                    if (exit_code := await reader.read(1)) == b"":
                        raise errors.OpenConnectTimeoutError()
                    elif (exit_code := int(exit_code)) == 0:
                        if output := (await reader.read()):
                            return orjson.loads(output)
                    elif exit_code == 3:
                        raise errors.UserExistError()
                    elif exit_code == 4:
                        raise errors.UserNotExistError()
                finally:
                    writer.close()
                    with suppress(BrokenPipeError):
                        await writer.wait_closed()
        except TimeoutError:
            raise errors.OpenConnectTimeoutError()

    async def _is_restarted(self) -> bool | None:
        """
        Whether the `OpenConnect` VPN server is
        restarted since the last time this method was called.

        For the very first time this method is executed, `None`
        will be returned because there is no way to determine
        whether this service is restarted before or not.
        """
        if status := await self._exec("show_status"):
            current_boot = status["raw_up_since"]
            if self._last_boot is None:
                self._last_boot = current_boot
                return None
            elif self._last_boot != current_boot:
                self._last_boot = current_boot
                return True

            return False

    async def _traffic_usage(
        self, username: str | None = None, reset: bool | None = None
    ) -> Traffic | dict[str, Traffic]:
        # There is no way to actually reset the client's traffic
        # usage on `OpenConnect` server side unlike the `Xray-core`.
        # Therefore, traffic usage should be tracked manually by
        # storing the traffic usage for each client and calculating
        # the difference on each method call.
        #
        # And again unlike the `Xray-core`, `OpenConnect` doesn't store
        # the previous traffic usages whenever the client reconnects.
        if not self._traffic_loaded:
            self._traffic_loaded = True
            if reset:
                try:
                    # Just ignoring the traffic stats prior to current time
                    await self._traffic_usage(username, reset)
                except:
                    self._traffic_loaded = False
                    raise
        elif await self._is_restarted():
            # The `OpenConnect` process is restarted.
            self._traffic.clear()

        stats = {}
        for user in (
            await self._exec(f"show_user{'s' if not username else f' {username}'}")
            or ()
        ):
            if user["State"] == "pre-auth":
                # `Username` property does not assigned in this stage yet
                continue

            _username = user["Username"]

            try:
                stats[_username]["uplink"] += int(user["TX"])
                stats[_username]["downlink"] += int(user["RX"])
            except KeyError:
                stats[_username] = {
                    "uplink": int(user["TX"]),
                    "downlink": int(user["RX"]),
                }

        traffic = {}
        for _username, _traffic in stats.items():
            uplink = _traffic["uplink"]
            downlink = _traffic["downlink"]

            try:
                _previous_traffic = self._traffic[_username]
            except KeyError:
                self._traffic[_username] = (
                    _traffic if reset else {"uplink": 0, "downlink": 0}
                )
            else:
                uplink -= _previous_traffic["uplink"]
                downlink -= _previous_traffic["downlink"]

                # Client was disconnected and reconnected again
                if uplink < 0:
                    uplink = _traffic["uplink"]
                if downlink < 0:
                    downlink = _traffic["downlink"]

                if reset:
                    _previous_traffic["uplink"] = _traffic["uplink"]
                    _previous_traffic["downlink"] = _traffic["downlink"]

            traffic[_username] = {"uplink": uplink, "downlink": downlink}

        if username and username in traffic:
            return traffic[username]
        return traffic

    async def add_user(self, username: str, uuid: str) -> None:
        await self._exec(f"add_user {username} {uuid}")
        logger.debug(f"User '{username}' is added")

    async def delete_user(self, username: str) -> None:
        await self._exec(f"delete_user {username}")
        logger.debug(f"User '{username}' is deleted")

    async def user_traffic_usage(self, username: str, reset: bool = True) -> Traffic:
        return await self._traffic_usage(username, reset)

    async def users_traffic_usage(self, reset: bool = True) -> dict[str, Traffic]:
        return await self._traffic_usage(reset=reset)
