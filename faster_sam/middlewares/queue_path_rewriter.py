import json
from http import HTTPStatus
import logging

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class QueuePathRewriterMiddleware:
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
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Response:
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
        request = Request(scope, receive=receive)

        if request.method != "POST":
            return await self.app(scope, receive, send)

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

        return await self.app(scope, receive, send)