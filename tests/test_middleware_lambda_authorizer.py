import json
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import lambda_authorizer

from unittest import mock
import io
from botocore.response import StreamingBody


def invokation_response(effect: str):
    response_payload = json.dumps(
        {
            "principalId": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": effect,
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


class TestLambdaAuthorizerMiddleware(unittest.IsolatedAsyncioTestCase):
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
            "http_version": "1.1",
            "method": "GET",
            "root_path": "",
            "query_string": [],
            "path_params": {},
            "path": "/test/foo",
            "client": ("127.0.0.1", 80),
            "app": FastAPI(),
            "headers": [
                # (b"host", b"localhost:8000"),
                # (b"user-agent", b"curl/7.81.0"),
                # (b"accept", b"*/*"),
                # (b"authorization", b"eyJhbGciOiJIUzI1.eyJib3Jyb4Ik1TF9.JKvZfg5LZ9L96k"),
                (b"content-type", b"application/json"),
                (b"user-agent", b"python/unittest"),
                (b"Authorization", b"eyJhbGciO.iJIUzI1NiIsInR5c.CI6IkpXVCJ9"),
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

    async def test_middleware_internal_server_error(self):
        request = Request(scope=self.scope)
        client_lambda = self.mock_boto.client.return_value
        client_lambda.invoke.side_effect = client_lambda.exceptions.ServiceException(
            error_response={
                "Error": {
                    "Code": "ServiceException",
                    "Message": "An error occurred (ServiceException) when calling the InvokeFunction operation (reached max retries: 4): An error occurred and the request cannot be processed.",  # noqa
                }
            },
            operation_name="InvokeFunction ",
        )
        response = await self.middleware.dispatch(request, lambda x: ...)
        body = json.loads(response.body)
        self.assertEqual(body["message"], "Something went wrong. Try again")
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.value)
