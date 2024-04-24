import json
from http import HTTPStatus
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class QueuePathRewriterMiddleware(BaseHTTPMiddleware):
    """
    Rewrites a specified part of the request path.

    Parameters
    ----------
    app : ASGIApp
        Application instance the middleware is being registered to.
    """

    def __init__(self, app: ASGIApp) -> None:
        """
        Initializes the QueuePathRewriterMiddleware.
        """
        super().__init__(app, self.dispatch)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Rewrites a specified part of the request path.

        Parameters
        ----------
        request : Request
            The incoming request.
        call_next : RequestResponseEndpoint
            Next middleware or endpoint on the execution stack.

        Returns
        -------
        Response
            The response generated by the middleware.
        """
        if request.method != "POST":
            return await call_next(request)

        body = await request.body()

        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            content = {"message": "Invalid Request"}
            status_code = HTTPStatus.BAD_REQUEST

            return Response(content=json.dumps(content), status_code=status_code.value)

        logger.debug(f"Received body: {body}")

        queue = body["message"]["attributes"]["endpoint"]

        if "/" in queue:
            queue = queue.rsplit("/")[-1]

        request.scope["path"] = "/" + queue

        return await call_next(request)
