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
    Represents an API Gateway HTTP response.
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
    Builds an event of type aws_proxy from API Gateway.

    It uses the given request object to fill the event details.

    Parameters
    ----------
    request : Request
        A request object.

    Returns
    -------
    Dict[str, Any]
        An aws_proxy event.
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
            "authorizer": request.scope.get("authorization_context"),
        },
    }

    return event


def handler(func: Handler) -> Endpoint:
    """
    Returns a wrapper function.

    The returning function converts a request object into a AWS proxy event,
    then the event is passed to the handler function,
    finally the function result is converted to a response object.

    Parameters
    ----------
    func : Handler
        A callable object.

    Returns
    -------
    Endpoint
        An async function, which accepts a single request argument and return a response.
    """

    async def wrapper(request: Request) -> Response:
        event = await event_builder(request)
        result = func(event, None)
        response = ApiGatewayResponse(result)

        return response

    return wrapper


def import_handler(path: str) -> Handler:
    """
    Returns a callable object from the given module path.

    Parameters
    ----------
    path : str
        Full module path.

    Returns
    -------
    Handler
        A callable object.
    """
    module_name, handler_name = path.rsplit(".", maxsplit=1)
    module = __import__(module_name, fromlist=(handler_name,))

    return getattr(module, handler_name)


class APIRoute(routing.APIRoute):
    """
    Extends FastAPI Router class used to describe path operations.

    This custom router class receives the endpoint parameter as a string with
    the full module path instead of the actual callable.
    """

    def __init__(self, path: str, endpoint: str, *args, **kwargs):
        """
        Initializes the APIRoute object.

        Parameters
        ----------
        path : str
            HTTP route path.
        endpoint : str
            Full module path.
        """
        handler_path = endpoint
        handler_func = import_handler(handler_path)
        super().__init__(path=path, endpoint=handler(handler_func), *args, **kwargs)
