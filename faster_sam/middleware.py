import json
from http import HTTPStatus
from typing import Dict, Optional

from botocore.client import BaseClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RemovePathMiddleware(BaseHTTPMiddleware):
    """
    Removes a specified part of the request path.

    e.g

    This example apply the middleware to transform the request path from "/foo/bar" to "/bar"
    by removing a specified part ("/foo").

    >>> app = FastAPI()
    >>> app.add_middleware(RemovePathMiddleware, path="/foo")
    >>> @app.get("/bar")
    ... def bar():
    ...     return {"message": "Responding to GET /foo/bar}

    Parameters
    ----------
        app : ASGIApp
            Application instance the middleware is being registered to.
        path : str
            The part of the path to be removed from incoming requests.
    """

    def __init__(self, app: ASGIApp, path: str) -> None:
        """
        Initializes the RemovePathMiddleware.
        """
        super().__init__(app, self.dispatch)
        self.path = path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Removes the specified part of the request path.

        Parameters
        ----------
        request : Request
            The incoming request.
        call_next : RequestResponseEndpoint
            Next middleware or endpoint on the execution stack

        Returns
        -------
        Response
            The response generated by the middleware.
        """

        request.scope["path"] = request.scope["path"].replace(self.path, "", 1)
        return await call_next(request)


class LambdaAuthorizer(BaseHTTPMiddleware):
    """
    Invoke lambda function in aws to authorize apis

    This example apply the middleware to authorize an app.

    >>> app = FastAPI()
    >>> app.add_middleware(LambdaAuthorizer, arn="arn:aws:lambda:region:id:function:name")
    Parameters
    ----------
        app : ASGIApp
            Application instance the middleware is being registered to.
        arn : str
            The amazon resource name for the lambda will be invoked.
        client: BaseClient
            Client lambda object
    """

    def __init__(self, app: ASGIApp, arn: str, client: Optional[BaseClient] = None) -> None:
        """
        Initializes the LambdaAuthorizer.
        """
        super().__init__(app, self.dispatch)
        self.arn = arn
        self.client = client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Authorize or deny a request based on Authorization field.

        Parameters
        ----------
        request : Request
            The incoming request.
        call_next : RequestResponseEndpoint
            Next middleware or endpoint on the execution stack

        Returns
        -------
        Response
            The response generated by the middleware.
        """

        response = self.invoke_lambda_authorization(request)

        if not response:
            return Response(
                content=json.dumps({"message": "Unauthorized"}),
                status_code=HTTPStatus.UNAUTHORIZED.value,
            )
        return await call_next(request)

    def invoke_lambda_authorization(self, request: Request) -> Dict[str, any]:
        """
        Invoke a Lambda using arn from aws.

        Parameters
        ----------
        request : Request
            The incoming request.
        Returns
        -------
        Response
            The response generated by aws lambda invoked.
        """
        return {}
