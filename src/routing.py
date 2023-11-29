import json
import logging
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Callable, Dict
from uuid import uuid4

from fastapi import Request, Response, routing

logger = logging.getLogger(__name__)

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]


class ApiGatewayResponse(Response):
    def __init__(self, data: Dict[str, Any]):
        super().__init__(
            content=data["body"],
            status_code=data["statusCode"],
            headers=data["headers"],
            media_type=data["headers"].get("Content-Type"),
        )


async def event_builder(request: Request) -> Dict[str, Any]:
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


def default_endpoint(request: Request) -> Response:
    logger.error(f"Executing default endpoint: {request.scope}")

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    media_type = "application/json"
    content = json.dumps({"error": "Invalid endpoint execution"})
    response = Response(status_code=status_code, media_type=media_type, content=content)

    return response


def import_handler(path: str) -> Handler:
    module_name, handler_name = path.rsplit(".", maxsplit=1)
    module = __import__(module_name, fromlist=(handler_name,))

    return getattr(module, handler_name)


class APIRoute(routing.APIRoute):
    def __init__(self, lambda_handler: Handler, *args, **kwargs):
        super().__init__(endpoint=default_endpoint, *args, **kwargs)
        self.lambda_handler = lambda_handler
