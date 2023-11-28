import json
import logging
from http import HTTPStatus
from typing import Any, Callable, Dict

from fastapi import Request, Response, routing

logger = logging.getLogger(__name__)

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]


def default_endpoint(request: Request) -> Response:
    logger.error(f"Executing default endpoint: {request.scope}")

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    media_type = "application/json"
    content = json.dumps({"error": "Invalid endpoint execution"})
    response = Response(status_code=status_code, media_type=media_type, content=content)

    return response


class APIRoute(routing.APIRoute):
    def __init__(self, lambda_handler: Handler, *args, **kwargs):
        super().__init__(endpoint=default_endpoint, *args, **kwargs)
        self.lambda_handler = lambda_handler

    def get_handler(self, path: str) -> Handler:
        module, handler_name = path.rsplit(".", maxsplit=1)
        module_handler = __import__(module, fromlist=(handler_name,))

        return getattr(module_handler, handler_name)
