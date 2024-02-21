import json
import unittest

from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import rewrite_path


class TestRewritePathMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_rewrite_path(self):
        async def receive():
            return {
                "type": "http.request",
                "body": b'{"message":{"attributes":{"endpoint":"aws/bar"}}}',
            }

        app = FastAPI()

        middleware = rewrite_path.RewritePathMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "POST", "path": "/foo"}, receive=receive)

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/bar"})

    async def test_middleware_rewrite_path_with_empty_body(self):
        async def receive():
            return {
                "type": "http.request",
                "body": b"",
            }

        app = FastAPI()

        middleware = rewrite_path.RewritePathMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "POST", "path": "/foo"}, receive=receive)

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"message": "Invalid Request"})

    async def test_middleware_rewrite_path_without_post(self):
        app = FastAPI()

        middleware = rewrite_path.RewritePathMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "GET", "path": "/foo"})

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/foo"})
