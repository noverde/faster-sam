import datetime
import io
import json
import unittest
from http import HTTPStatus
from unittest import mock

from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from fastapi import FastAPI, Request, Response

from faster_sam.middlewares import lambda_authorizer


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

        self.aws_response = {
            "Credentials": {
                "AccessKeyId": "154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SecretAccessKey": "51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SessionToken": "sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "Expiration": datetime.datetime(
                    2024, 1, 18, 15, 20, 17, tzinfo=datetime.timezone.utc
                ),
            },
            "SubjectFromWebIdentityToken": "225554488662322215444",
            "AssumedRoleUser": {
                "AssumedRoleId": "AROAYADG7OK3I5GGAIWYS:my-role-session-name",
                "Arn": "arn:aws:sts::22555448866:assumed-role/role-to-assume/my-role-session-name",
            },
            "Provider": "accounts.google.com",
            "Audience": "225554488662322215444",
            "ResponseMetadata": {
                "RequestId": "3412e653-78f1-4754-9a08-9446df59fefe",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "3412e653-78f1-4754-9a08-9446df59fefe",
                    "content-type": "text/xml",
                    "content-length": "1425",
                    "date": "Thu, 18 Jan 2024 14:20:16 GMT",
                },
                "RetryAttempts": 0,
            },
        }

        self.mock_boto.client.return_value.assume_role_with_web_identity.return_value = (
            self.aws_response
        )

        app = FastAPI()

        credentials = lambda_authorizer.Credentials(
            role_arn="arn:aws:iam::22555448866:role/role-to-assume",
            web_identity_token="eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi",
            role_session_name="my-role-session-name",
        )

        self.middleware = lambda_authorizer.LambdaAuthorizerMiddleware(
            app, "arn:aws:lambda:region:account-id:function:function-name", credentials
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
                (b"host", b"localhost:8000"),
                (b"user-agent", b"curl/7.81.0"),
                (b"accept", b"*/*"),
                (b"authorization", b"eyJhbGciOiJIUzI1.eyJib3Jyb4Ik1TF9.JKvZfg5LZ9L96k"),
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

        client_lambda.invoke.side_effect = ClientError(
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


class TestLambdaClient(unittest.TestCase):
    def setUp(self) -> None:
        self.boto_patch = mock.patch("faster_sam.middlewares.lambda_authorizer.boto3")
        self.mock_boto = self.boto_patch.start()

        self.aws_response = {
            "Credentials": {
                "AccessKeyId": "154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SecretAccessKey": "51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SessionToken": "sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "Expiration": datetime.datetime(
                    2024, 1, 18, 15, 20, 17, tzinfo=datetime.timezone.utc
                ),
            },
            "SubjectFromWebIdentityToken": "225554488662322215444",
            "AssumedRoleUser": {
                "AssumedRoleId": "AROAYADG7OK3I5GGAIWYS:my-role-session-name",
                "Arn": "arn:aws:sts::22555448866:assumed-role/role-to-assume/my-role-session-name",
            },
            "Provider": "accounts.google.com",
            "Audience": "225554488662322215444",
            "ResponseMetadata": {
                "RequestId": "3412e653-78f1-4754-9a08-9446df59fefe",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "3412e653-78f1-4754-9a08-9446df59fefe",
                    "content-type": "text/xml",
                    "content-length": "1425",
                    "date": "Thu, 18 Jan 2024 14:20:16 GMT",
                },
                "RetryAttempts": 0,
            },
        }

        self.mock_boto.client.return_value.assume_role_with_web_identity.return_value = (
            self.aws_response
        )

        self.common_credentials = {
            "role_arn": "arn:aws:iam::22555448866:role/role-to-assume",
            "role_session_name": "my-role-session-name",
            "region": "region1",
        }

        self.credentials_with_web_token = lambda_authorizer.Credentials(
            web_identity_token="eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi",
            **self.common_credentials,
        )

        def web_identity_callable():
            return "eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi"

        self.credentials_with_web_token_function = lambda_authorizer.Credentials(
            web_identity_callable=web_identity_callable, **self.common_credentials
        )

        self.credentials_with_session_token = lambda_authorizer.Credentials(
            access_key="154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            secret_access_key="51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            session_token="sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            region="region1",
        )

    def tearDown(self) -> None:
        self.boto_patch.stop()

    def initialize_lambda_client(self, credentials):
        return lambda_authorizer.LambdaClient(credentials)

    def test_assume_role_with_token(self):
        client = self.initialize_lambda_client(self.credentials_with_web_token)
        credentials = client.assume_role()

        self.assertEqual(credentials, self.credentials_with_session_token)

    def test_assume_role_with_function(self):
        client = self.initialize_lambda_client(self.credentials_with_web_token_function)
        credentials = client.assume_role()

        self.assertEqual(credentials, self.credentials_with_session_token)

    def test_set_client(self):
        client = self.initialize_lambda_client(self.credentials_with_web_token)
        client.set_client()

        self.mock_boto.client.assert_called_with(
            "lambda",
            aws_access_key_id=self.credentials_with_session_token.access_key,
            aws_secret_access_key=self.credentials_with_session_token.secret_access_key,
            aws_session_token=self.credentials_with_session_token.session_token,
            region_name=self.credentials_with_web_token.region,
        )
