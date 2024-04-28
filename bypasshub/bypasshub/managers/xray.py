import logging
import functools
from io import StringIO
from typing import Self
from pathlib import Path
from urllib.parse import quote
from collections.abc import Awaitable, Callable

import grpc.aio
from grpc import StatusCode
from google.protobuf.message import Message
from xray_rpc.common.protocol.user_pb2 import User
from xray_rpc.proxy.vless.account_pb2 import Account
from xray_rpc.common.serial.typed_message_pb2 import TypedMessage
from xray_rpc.app.stats.command.command_pb2_grpc import StatsServiceStub
from xray_rpc.app.stats.command.command_pb2 import QueryStatsRequest
from xray_rpc.app.proxyman.command.command_pb2_grpc import HandlerServiceStub
from xray_rpc.app.proxyman.command.command_pb2 import (
    AlterInboundRequest,
    AddUserOperation,
    RemoveUserOperation,
)

from .base import BaseService
from .. import errors
from ..types import Traffic
from ..config import config
from ..constants import XrayService

timeout = config["main"]["service_timeout"]
domain = config["environment"]["domain"]
tls_port = config["environment"]["tls_port"]
cdn_tls_port = config["environment"]["cdn_tls_port"]
enable_xray_cdn = config["environment"]["enable_xray_cdn"]
xray_sni = config["environment"]["xray_sni"]
xray_cdn_sni = config["environment"]["xray_cdn_sni"]
xray_cdn_ips_path = Path(config["main"]["xray_cdn_ips_path"])
xray_api_socket_path = Path(config["main"]["xray_api_socket_path"])
xray_flow = "xtls-rprx-vision"
xray_inbounds = ["vless-tcp"]
if enable_xray_cdn:
    xray_inbounds.append("vless-ws")

logger = logging.getLogger(__name__)


class Xray(BaseService):
    """
    The `Xray-core` proxy server service.

    NOTE:   The `Xray-core` uses `gRPC` for its API.
            The `gRPC` Python implementation requires the process not to be
            forked before establishing the connection. Therefore, this class
            must not be instantiated before forking the running process.
            See: https://github.com/grpc/grpc/tree/master/examples/python/multiprocessing

    Attributes:
        `timeout`:
            The time in seconds to wait for the communications to the
            service to be finished. After that, ``errors.XrayTimeoutError``
            will be raised.
            `ValueError` will be raised if value is not a positive number.
            The default value is equal to `service_timeout` property of the
            configuration file.
    """

    NAME = XrayService.NAME
    ALIAS = XrayService.ALIAS

    def __init__(self, timeout: int | float = timeout) -> None:
        self.timeout = timeout
        if self.timeout <= 0:
            raise ValueError("The 'timeout' parameter should be greater than zero")

        self._channel = grpc.aio.insecure_channel(f"unix:{xray_api_socket_path}")
        self._stats_stub = StatsServiceStub(self._channel)
        self._proxyman_stub = HandlerServiceStub(self._channel)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exception) -> None:
        await self.close()

    def _exception_handler[**P, R](
        method: Callable[P, Awaitable[R]]
    ) -> Callable[P, Awaitable[R]]:
        """Handles the common exceptions for the passed method."""

        @functools.wraps(method)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await method(*args, **kwargs)
            except grpc.aio.AioRpcError as error:
                if "already exists" in (details := error.details().lower()):
                    raise errors.UserExistError()
                elif "not found" in details:
                    raise errors.UserNotExistError()
                elif (
                    "no such file or directory" in details
                    or "connection refused" in details
                    or error.code() == StatusCode.DEADLINE_EXCEEDED
                ):
                    raise errors.XrayTimeoutError()
                raise

        return wrapper

    def _typed_message(self, message: Message) -> TypedMessage:
        return TypedMessage(
            type=message.DESCRIPTOR.full_name, value=message.SerializeToString()
        )

    @_exception_handler
    async def add_user(self, username: str, uuid: str) -> None:
        for tag in xray_inbounds:
            await self._proxyman_stub.AlterInbound(
                AlterInboundRequest(
                    tag=tag,
                    operation=self._typed_message(
                        AddUserOperation(
                            user=User(
                                email=f"{username}@{domain}",
                                account=self._typed_message(
                                    Account(id=uuid, flow=xray_flow)
                                ),
                            )
                        )
                    ),
                ),
                timeout=self.timeout,
            )
        logger.debug(f"User '{username}' is added")

    @_exception_handler
    async def delete_user(self, username: str) -> None:
        for tag in xray_inbounds:
            await self._proxyman_stub.AlterInbound(
                AlterInboundRequest(
                    tag=tag,
                    operation=self._typed_message(
                        RemoveUserOperation(email=f"{username}@{domain}")
                    ),
                ),
                timeout=self.timeout,
            )
        logger.debug(f"User '{username}' is deleted")

    @_exception_handler
    async def user_traffic_usage(self, username: str, reset: bool = True) -> Traffic:
        return {
            stat.name.split(">>>")[-1]: stat.value
            for stat in (
                await self._stats_stub.QueryStats(
                    QueryStatsRequest(
                        pattern=f"user>>>{username}@{domain}>>>traffic", reset=reset
                    ),
                    timeout=self.timeout,
                )
            ).stat
        }

    @_exception_handler
    async def users_traffic_usage(self, reset: bool = True) -> dict[str, Traffic]:
        stats = {}
        for stat in (
            await self._stats_stub.QueryStats(
                QueryStatsRequest(pattern="user", reset=reset), timeout=self.timeout
            )
        ).stat:
            sections = stat.name.split(">>>")
            username = sections[1].split("@")[0]
            try:
                stats[username][sections[-1]] = stat.value
            except KeyError:
                stats[username] = {sections[-1]: stat.value}

        return stats

    async def close(self) -> None:
        """Closes the connection to the service."""
        await self._channel.close(self.timeout)

    @staticmethod
    def generate_subscription(uuid: str) -> str:
        """Generates `V2Ray` compatible config URLs for the given `UUID`."""
        shared = "?security=tls&fp=randomized"
        stream = StringIO()
        try:
            stream.write(
                (
                    f"vless://{uuid}@{xray_sni}:{tls_port}{shared}"
                    f"&type=tcp&flow=xtls-rprx-vision#{domain}\n"
                )
            )
            if enable_xray_cdn:
                cdn_port = cdn_tls_port or tls_port
                url_ws = (
                    f":{cdn_port}{shared}&type=ws&sni={xray_cdn_sni}"
                    f"&host={xray_cdn_sni}&path={quote('/ws?ed=2560')}"
                    f"#{domain}-CDN"
                )
                stream.write(f"vless://{uuid}@{xray_cdn_sni}{url_ws}\n")
                if xray_cdn_ips_path.exists():
                    items = iter(xray_cdn_ips_path.read_text().split())
                    for ip, tag in zip(items, items):
                        stream.write(f"vless://{uuid}@{ip}{url_ws}-{tag}\n")

            return stream.getvalue()
        finally:
            stream.close()
