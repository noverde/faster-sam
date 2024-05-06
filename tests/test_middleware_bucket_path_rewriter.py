import json
import unittest

from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import bucket_path_rewriter


class TestBucketPathRewriterMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_rewrite_path_with_bucket(self):
        async def receive():
            return {
                "type": "http.request",
                "body": b'{"bucket":"test-bucket-123"}',
            }

        app = FastAPI()

        middleware = bucket_path_rewriter.BucketPathRewriterMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "POST", "path": "/"}, receive=receive)

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/test-bucket-123"})

    async def test_middleware_rewrite_path_with_empty_body(self):
        async def receive():
            return {
                "type": "http.request",
                "body": b"",
            }

        app = FastAPI()

        middleware = bucket_path_rewriter.BucketPathRewriterMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "POST", "path": "/"}, receive=receive)

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"message": "Invalid Request"})

    async def test_middleware_rewrite_path_without_post(self):
        app = FastAPI()

        middleware = bucket_path_rewriter.BucketPathRewriterMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "GET", "path": "/"})

        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/"})
