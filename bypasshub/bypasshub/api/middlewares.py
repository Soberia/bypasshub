import re
from typing import Annotated
from secrets import compare_digest

from fastapi import Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyQuery, APIKeyHeader
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .utils import http_not_found
from ..config import config


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """The middleware that authenticate the requests.

    The API key could be provided as a query parameter or as a header.
    The query parameter and header names that should be included in the
    request is respectively equal to the ``self.query`` and ``self.header``
    properties.

    If the provided key is valid, the response will be returned.
    Otherwise, HTTP 404 error will be returned as response instead.

    Requests for the Swagger UI HTML response or the OpenAPI schema JSON
    response also go through the authentication process. So, the API key
    for these endpoints also needed to be provided.
    """

    _QUERY = "api-key"
    _HEADER = "X-API-Key"
    _api_key_query = APIKeyQuery(name=_QUERY, auto_error=False)
    _api_key_header = APIKeyHeader(name=_HEADER, auto_error=False)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> JSONResponse:
        root_path = request.app.root_path.rstrip()
        for method in (self._api_key_query, self._api_key_header):
            api_key = await method(request)
            if api_key is not None and compare_digest(
                api_key.encode(), config["api"]["key"]
            ):
                if request.app.openapi_url and (
                    request.url.path == (root_path + request.app.docs_url)
                ):
                    if "onComplete" not in (
                        parameters := request.app.swagger_ui_parameters
                    ):
                        parameters["persistAuthorization"] = False
                        parameters["onComplete"] = (
                            "() => ui.preauthorizeApiKey("
                            f"'{self._api_key_query.__class__.__name__}', "
                            f"location.search.match(/{self.query}=(?<key>.*)/i)?.groups.key)"
                        )

                    response = get_swagger_ui_html(
                        openapi_url=(
                            f"{root_path}{request.app.openapi_url}"
                            f"?{self.query}={api_key}"
                        ),
                        title=request.app.title,
                        swagger_ui_parameters=parameters,
                        swagger_favicon_url=config["api"]["ui_icon"],
                    )

                    # Removing the string quotes because the value is a function.
                    # After the modification, the `content-length` header also
                    # should be corrected to represent the correct size.
                    response.body = re.sub(
                        b'("onComplete": )"(.*)"', b"\\1\\2", response.body
                    )
                    response.headers["content-length"] = str(len(response.body))

                    return response

                return await call_next(request)

        return await http_not_found()

    @staticmethod
    async def schema(
        api_key_query: Annotated[str, Security(_api_key_query)],
        api_key_header: Annotated[str, Security(_api_key_header)],
    ) -> None:
        """
        This should be passed as a dependency to the `FastAPI` app
        instance to generate OpenAPI schema with the security filed.
        """
        pass

    @property
    def query(self) -> str:
        """The query parameter name."""
        return self._QUERY

    @property
    def header(self) -> str:
        """The header name."""
        return self._HEADER
