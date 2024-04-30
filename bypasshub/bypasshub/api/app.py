import logging
from contextlib import suppress, asynccontextmanager
from collections.abc import AsyncGenerator
from asyncio.exceptions import CancelledError

from uvicorn import Server, Config
from fastapi import FastAPI, Request, Depends
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse, ORJSONResponse, PlainTextResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as DefaultHTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from .utils import http_not_found
from .middlewares import AuthenticationMiddleware
from .routers import user, info, database, subscription
from .. import __version__, __homepage__
from ..config import config
from ..managers import Manager
from ..types import HTTPSerializedError
from ..errors import BaseError, UnexpectedError

enable_api = config["api"]["enable"]
enable_xray_subscription = config["environment"]["enable_xray_subscription"]

logger = logging.getLogger(__name__)
app = FastAPI(default_response_class=ORJSONResponse, openapi_url=None)
app_api = FastAPI(
    middleware=[Middleware(AuthenticationMiddleware)],
    dependencies=[Depends(AuthenticationMiddleware.schema)],
    responses={
        HTTP_400_BAD_REQUEST: (model := {"model": HTTPSerializedError}),
        HTTP_500_INTERNAL_SERVER_ERROR: model,
    },
    default_response_class=ORJSONResponse,
    version=__version__,
    title="BypassHub API",
    contact={"url": __homepage__},
    license_info={"name": "MIT License", "url": f"{__homepage__}/blob/main/LICENSE"},
    root_path="/api",
    openapi_url="/openapi.json" if config["api"]["ui"] else None,
    docs_url="/",
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
    swagger_ui_parameters={
        "filter": True,
        "tryItOutEnabled": True,
        "displayRequestDuration": True,
    },
)


@app.exception_handler(RequestValidationError)
@app.exception_handler(DefaultHTTPException)
@app.exception_handler(Exception)
async def exception_handler(*args) -> PlainTextResponse:
    return await http_not_found()


@app_api.exception_handler(BaseError)
async def exception_handler(request: Request, exc: BaseError) -> JSONResponse:
    return await http_exception_handler(
        request, HTTPException(exc.http_code, exc.serialize())
    )


@app_api.exception_handler(ExceptionGroup)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    exc = (
        exc.exceptions[0]
        if len(exc.exceptions) == 1 and isinstance(exc.exceptions[0], BaseError)
        else UnexpectedError(cause=exc)
    )

    return await http_exception_handler(
        request, HTTPException(exc.http_code, exc.serialize())
    )


@app_api.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    exc = UnexpectedError(cause=exc)
    return await http_exception_handler(
        request, HTTPException(exc.http_code, exc.serialize())
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("The worker process is started")
    app.state.manager = app_api.state.manager = Manager()

    # If `SIGINT` signal received before application startup,
    # `CancelledError` would be raised in here and prevents
    # the proper application shutdown.
    # See https://github.com/encode/uvicorn/discussions/1662
    with suppress(CancelledError):
        yield

    await app.state.manager.close()
    logger.info("The worker process is stopped")


async def run() -> None:
    """Runs the server."""
    if not enable_xray_subscription and not enable_api:
        return

    app.router.lifespan_context = lifespan
    if enable_xray_subscription:
        app.include_router(subscription.router)
    if enable_api:
        app.mount(app_api.root_path, app_api, "api")
        for router in (user, info, database, subscription):
            app_api.include_router(router.router)

    await Server(
        Config(
            app,
            uds=config["api"]["socket_path"],
            timeout_graceful_shutdown=config["api"]["graceful_timeout"],
            timeout_keep_alive=15,
            workers=1,
            backlog=2048,
            log_config=None,  # Already configured
            date_header=False,
            server_header=False,
            forwarded_allow_ips="*",
        )
    ).serve()
