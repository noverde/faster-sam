import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict
from uuid import uuid4

from fastapi import Request, Response, routing

logger = logging.getLogger(__name__)

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]
Endpoint = Callable[[Request], Awaitable[Response]]


class ApiGatewayResponse(Response):
    """
    Represents an API Gateway http response.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initializes the ApiGatewayResponse.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary containing the response data.
        """

        super().__init__(
            content=data["body"],
            status_code=data["statusCode"],
            headers=data.get("headers"),
            media_type=data.get("headers", {}).get("Content-Type"),
        )


async def event_builder(request: Request) -> Dict[str, Any]:
    """
    Builds an event dictionary from the given request.

    Parameters
    ----------
    request : Request
        The application request.

    Returns
    -------
    Dict[str, Any]
        The event dictionary.
    """

    now = datetime.now(timezone.utc)
    body = await request.body()
    event = {
        "body": body.decode(),
        "path": request.url.path,
        "httpMethod": request.method,
        "isBase64Encoded": False,
        "queryStringParameters": dict(request.query_params),
        "pathParameters": dict(request.path_params),
        "headers": dict(request.headers),
        "requestContext": {
            "stage": request.app.version,
            "requestId": str(uuid4()),
            "requestTime": now.strftime(r"%d/%b/%Y:%H:%M:%S %z"),
            "requestTimeEpoch": int(now.timestamp()),
            "identity": {
                "sourceIp": getattr(request.client, "host", None),
                "userAgent": request.headers.get("user-agent"),
            },
            "path": request.url.path,
            "httpMethod": request.method,
            "protocol": f"HTTP/{request.scope['http_version']}",
        },
    }

    return event


def handler(func: Handler) -> Endpoint:
    async def wrapper(request: Request) -> Response:
        event = await event_builder(request)
        result = func(event, None)
        response = ApiGatewayResponse(result)

        return response

    return wrapper


def import_handler(path: str) -> Handler:
    module_name, handler_name = path.rsplit(".", maxsplit=1)
    module = __import__(module_name, fromlist=(handler_name,))

    return getattr(module, handler_name)


class APIRoute(routing.APIRoute):
    def __init__(self, path: str, endpoint: str, *args, **kwargs):
        handler_path = endpoint
        handler_func = import_handler(handler_path)
        super().__init__(path=path, endpoint=handler(handler_func), *args, **kwargs)
