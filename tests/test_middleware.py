import json
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import lambda_authorizer, remove_path

from unittest import mock
import io
from botocore.response import StreamingBody


def invokation_response(type: str):
    response_payload = json.dumps(
        {
            "principalId": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": type,
                        "Resource": ["arn:aws:execute-api:us-east4:xpl3tuf2r0/v1/*/*"],
                    }
                ],
            },
            "context": {},
        }
    )

    response = {
        "StatusCode": 200,
        "LogResult": "asdfg==",
        "ExecutedVersion": "$LATEST",
        "Payload": StreamingBody(
            raw_stream=io.BytesIO(response_payload.encode()),
            content_length=len(response_payload),
        ),
    }
    return response


class TestRemovePathMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_middleware_remove_path(self):
        app = FastAPI()

        middleware = remove_path.RemovePathMiddleware(app, path="/test")

        async def call_next(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        request = Request(scope={"type": "http", "method": "GET", "path": "/test/foo"})
        response = await middleware.dispatch(request, call_next)

        self.assertEqual(json.loads(response.body), {"path": "/foo"})


class TestLambdaAuthorizer(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.boto_patch = mock.patch("faster_sam.middlewares.lambda_authorizer.boto3")
        self.mock_boto = self.boto_patch.start()

        app = FastAPI()

        self.middleware = lambda_authorizer.LambdaAuthorizerMiddleware(
            app,
            "arn:aws:lambda:region:account-id:function:function-name",
        )

        self.scope = {
            "type": "http",
            "method": "GET",
            "path": "/test/foo",
            "headers": [
                (b"content-type", b"application/json"),
                (b"user-agent", b"python/unittest"),
                (
                    b"Authorization",
                    b"eyJhbGciO.iJIUzI1NiIsInR5c.CI6IkpXVCJ9",
                ),
            ],
        }

    def tearDown(self) -> None:
        self.boto_patch.stop()

    async def test_middleware_unauthorized(self):
        request = Request(scope=self.scope)

        mocked_invokation_response = invokation_response("Deny")
        self.mock_boto.client.return_value.invoke.return_value = mocked_invokation_response

        response = await self.middleware.dispatch(request, lambda x: ...)
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Unauthorized")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED.value)

    async def test_middleware_authorized(self):
        async def call_next(request: Request) -> Response:
            return Response(
                content=json.dumps({"message": "Authorized"}), status_code=HTTPStatus.OK.value
            )

        request = Request(scope=self.scope)

        mocked_invokation_response = invokation_response("Allow")
        self.mock_boto.client.return_value.invoke.return_value = mocked_invokation_response

        response = await self.middleware.dispatch(request, call_next)
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Authorized")
        self.assertEqual(response.status_code, HTTPStatus.OK.value)
