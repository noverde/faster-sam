from http import HTTPStatus
import json
import unittest

from fastapi import FastAPI, Request, Response

from faster_sam.middleware import LambdaAuthorizer, RemovePathMiddleware


class TestRemovePathMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_remove_path(self):
        app = FastAPI()

        middleware = RemovePathMiddleware(app, path="/test")

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "GET", "path": "/test/foo"})
        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/foo"})


class TestLambdaAuthorizer(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_unauthorized(self):
        app = FastAPI()

        middleware = LambdaAuthorizer(
            app,
            "arn:aws:lambda:region:account-id:function:function-name",
        )

        async def call_next(request: Request) -> Response:
            pass

        request = Request(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/test/foo",
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"user-agent", b"python/unittest"),
                    (
                        b"Authorization",
                        b"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJib3Jyb3dlcl9pZCI6NDM3MSwiY3Bm",
                    ),
                ],
            }
        )
        response = await middleware.dispatch(request, call_next)
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Unauthorized")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED.value)
