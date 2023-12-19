from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RemovePathMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, path: str) -> None:
        super().__init__(app, self.dispatch)
        self.path = path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.scope["path"] = request.scope["path"].replace(self.path, "", 1)
        return await call_next(request)
