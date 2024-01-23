import json
import unittest

from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import remove_path


class TestRemovePathMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_remove_path(self):
        app = FastAPI()

        middleware = remove_path.RemovePathMiddleware(app, path="/test")

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "GET", "path": "/test/foo"})
        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/foo"})
