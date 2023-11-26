import re
import logging

import httpx
from pydantic import ValidationError
from pydantic_core import PydanticCustomError, InitErrorDetails
from fastapi import Response
from fastapi.responses import PlainTextResponse
from fastapi.exceptions import RequestValidationError
from starlette.status import HTTP_404_NOT_FOUND

from ..config import config

domain = config["environment"]["domain"]
nginx_fallback_socket_path = config["main"]["nginx_fallback_socket_path"]
logger = logging.getLogger(__name__)


def value_error_converter(error: ValueError) -> RequestValidationError:
    """Converts `ValueError` to `RequestValidationError`."""
    return RequestValidationError(
        errors=(
            ValidationError.from_exception_data(
                "ValueError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "value-error", message := str(error).replace("_", "-")
                        ),
                        loc=("body", re.search(r"'(.*)'", message).group(1)),
                    )
                ],
            )
        ).errors()
    )


async def http_not_found() -> Response | PlainTextResponse:
    """Returns the default HTTP 404 error response from the `NGINX` HTTP server"""
    try:
        async with httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=1,
                max_keepalive_connections=1,  # Denying the pool
            ),
            transport=httpx.AsyncHTTPTransport(
                uds=nginx_fallback_socket_path, retries=1
            ),
        ) as client:
            response = await client.get(f"http://{domain}/404")
            return Response(
                content=await response.aread(),
                status_code=response.status_code,
                headers=response.headers,
            )
    except Exception as error:
        logger.exception(
            (
                "Something went wrong when tried to get the default"
                " HTTP 404 error response from the 'NGINX' HTTP server"
            ),
            exc_info=error,
        )
        return PlainTextResponse(
            content=b"Nothing Found", status_code=HTTP_404_NOT_FOUND
        )
