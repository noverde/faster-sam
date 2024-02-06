import copy
import io
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest import mock

from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from fastapi import FastAPI, Request, Response
from requests import Response as RequestResponse
from faster_sam.cache.redis import RedisCache

from faster_sam.middlewares import lambda_authorizer
from tests.test_redis import FakeRedis


def call_next_function(response: Response = Response()):
    async def call_next(_: Request) -> Response:
        return response

    return call_next


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
        self.aws_session = self.mock_boto.Session
        self.lambda_cli = self.aws_session.return_value.client
        self.sts_cli = self.mock_boto.client

        self.redis_patch = mock.patch("faster_sam.cache.redis.redis")
        self.redis_mock = self.redis_patch.start()
        self.redis_mock.Redis.from_url.return_value = FakeRedis()

        self.aws_response = {
            "Credentials": {
                "AccessKeyId": "154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SecretAccessKey": "51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SessionToken": "sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "Expiration": datetime.now(tz=timezone.utc) + timedelta(minutes=2),
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

        self.sts_cli.return_value.assume_role_with_web_identity.return_value = self.aws_response

        app = FastAPI()

        credentials = lambda_authorizer.Credentials(
            role_arn="arn:aws:iam::22555448866:role/role-to-assume",
            web_identity_token="eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi",
            role_session_name="my-role-session-name",
        )

        self.middleware = lambda_authorizer.LambdaAuthorizerMiddleware(
            app, "arn:aws:lambda:region:account-id:function:function-name", credentials
        )

        self.redis = RedisCache()

        self.middleware_with_cache = lambda_authorizer.LambdaAuthorizerMiddleware(
            app, "arn:aws:lambda:region:account-id:function:function-name", credentials, self.redis
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
        RedisCache()._get_connection().flushdb()
        self.boto_patch.stop()
        self.redis_patch.stop()

    async def test_middleware_unauthorized(self):
        request = Request(scope=self.scope)
        self.lambda_cli.return_value.invoke.return_value = invokation_response("Deny")

        response = await self.middleware.dispatch(request, call_next_function())
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Unauthorized")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED.value)

    async def test_middleware_authorized(self):
        call_next_response = Response(
            content=json.dumps({"message": "Authorized"}), status_code=HTTPStatus.OK.value
        )
        call_next = call_next_function(call_next_response)
        request = Request(scope=self.scope)

        self.lambda_cli.return_value.invoke.return_value = invokation_response("Allow")

        response = await self.middleware.dispatch(request, call_next)
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Authorized")
        self.assertEqual(response.status_code, HTTPStatus.OK.value)

    async def test_middleware_internal_server_error(self):
        request = Request(scope=self.scope)

        self.lambda_cli.return_value.invoke.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ServiceException",
                    "Message": "An error occurred (ServiceException) when calling the InvokeFunction operation (reached max retries: 4): An error occurred and the request cannot be processed.",  # noqa
                }
            },
            operation_name="InvokeFunction ",
        )

        response = await self.middleware.dispatch(request, call_next_function())
        body = json.loads(response.body)

        self.assertEqual(body["message"], "Something went wrong. Try again")
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.value)


class TestLambdaClient(unittest.TestCase):
    def setUp(self) -> None:
        self.boto_patch = mock.patch("faster_sam.middlewares.lambda_authorizer.boto3")
        self.mock_boto = self.boto_patch.start()
        self.aws_session = self.mock_boto.Session
        self.lambda_cli = self.aws_session.return_value.client
        self.sts_cli = self.mock_boto.client

        self.requests_patch = mock.patch("faster_sam.web_identity_providers.requests")
        self.requests_mock = self.requests_patch.start()

        response = RequestResponse()
        response.status_code = HTTPStatus.OK.value
        response._content = b"eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi"
        self.requests_mock.get.return_value = response

        self.aws_response = {
            "Credentials": {
                "AccessKeyId": "154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SecretAccessKey": "51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "SessionToken": "sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
                "Expiration": datetime.now(tz=timezone.utc) + timedelta(minutes=2),
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

        self.sts_cli.return_value.assume_role_with_web_identity.return_value = self.aws_response

        self.credentials_with_web_token = lambda_authorizer.Credentials(
            web_identity_token="eyJhbGciOiJSUzI1Ni.eyJhdWQiOiJodHRwczov.b25hd3MuY29tIi",
            role_arn="arn:aws:iam::22555448866:role/role-to-assume",
            role_session_name="my-role-session-name",
            region="us-east-1",
        )

        self.credentials_with_web_token_function = lambda_authorizer.Credentials(
            role_arn="arn:aws:iam::22555448866:role/role-to-assume",
            role_session_name="my-role-session-name",
            web_identity_provider="gcp",
            region="us-east-1",
        )

        self.credentials_with_session_token = lambda_authorizer.Credentials(
            access_key_id="154vc8sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            secret_access_key="51fd5g4sdsdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            session_token="sdffBG45W$#6f$56%W$W%V5$BWVE787Trdg",
            region="us-east-1",
        )

    def tearDown(self) -> None:
        self.boto_patch.stop()
        self.requests_patch.stop()

    def test_assume_role(self):
        web_token = {
            "credentials_with_web_token": self.credentials_with_web_token,
            "credentials_with_web_token_function": self.credentials_with_web_token_function,
        }

        for use_case, token_type in web_token.items():
            with self.subTest(use_case=use_case):
                client = lambda_authorizer.LambdaClient(token_type)
                credentials = client.assume_role()

                self.assertEqual(credentials, self.credentials_with_session_token)

    def test_set_client(self):
        client = lambda_authorizer.LambdaClient(self.credentials_with_web_token)
        client.set_client()

        self.aws_session.assert_called_with(
            aws_access_key_id=self.credentials_with_session_token.access_key_id,
            aws_secret_access_key=self.credentials_with_session_token.secret_access_key,
            aws_session_token=self.credentials_with_session_token.session_token,
            region_name=self.credentials_with_web_token.region,
            profile_name=self.credentials_with_web_token.profile,
        )
        self.lambda_cli.assert_called_with("lambda")

    def test_set_client_with_acsess_key(self):
        client = lambda_authorizer.LambdaClient(self.credentials_with_session_token)
        client.set_client()

        self.assertEqual(client.expired, False)
        self.aws_session.assert_called_with(
            aws_access_key_id=self.credentials_with_session_token.access_key_id,
            aws_secret_access_key=self.credentials_with_session_token.secret_access_key,
            aws_session_token=self.credentials_with_session_token.session_token,
            region_name=self.credentials_with_web_token.region,
            profile_name=self.credentials_with_web_token.profile,
        )
        self.lambda_cli.assert_called_with("lambda")

    def test_expired_false(self):
        client = lambda_authorizer.LambdaClient(self.credentials_with_web_token)
        client.set_client()

        self.assertEqual(client.expired, False)

    def test_expired_true(self):
        response = self.aws_response
        response["Credentials"]["Expiration"] = datetime.now(tz=timezone.utc)
        self.sts_cli.assume_role_with_web_identity.return_value = response

        client = lambda_authorizer.LambdaClient(self.credentials_with_web_token)
        client.set_client()

        self.assertEqual(client.expired, True)

    def test_expired_refresh(self):
        response = copy.deepcopy(self.aws_response)
        response["Credentials"]["Expiration"] = datetime.now(tz=timezone.utc)

        self.sts_cli.return_value.assume_role_with_web_identity.side_effect = [
            response,
            self.aws_response,
        ]

        client = lambda_authorizer.LambdaClient(self.credentials_with_web_token)

        self.assertIsNotNone(client.client)
        self.assertEqual(client.expired, False)


@mock.patch.dict(
    "os.environ",
    {
        "AWS_ROLE_ARN": "arn:aws:iam::22555448866:role/role-from-environment",
        "AWS_WEB_IDENTITY_PROVIDER": "gcp-environment",
        "AWS_ROLE_SESSION_NAME": "my-role-session-name-environment",
        "AWS_REGION": "us-east-1-environment",
    },
)
class TestCredentials(unittest.TestCase):
    def test_load_credentials_from_environment(self):
        credentials = lambda_authorizer.Credentials()

        self.assertEqual(credentials.role_arn, os.environ["AWS_ROLE_ARN"])
        self.assertEqual(credentials.web_identity_provider, os.environ["AWS_WEB_IDENTITY_PROVIDER"])
        self.assertEqual(credentials.role_session_name, os.environ["AWS_ROLE_SESSION_NAME"])
        self.assertEqual(credentials.region, os.environ["AWS_REGION"])

    def test_credentials(self):
        role_arn = "arn:aws:iam::22555448866:role/role-to-assume"
        web_identity_provider = "gcp"
        role_session_name = "my-role-session-name"
        region = "us-east-1"

        credentials = lambda_authorizer.Credentials(
            role_arn=role_arn,
            web_identity_provider=web_identity_provider,
            role_session_name=role_session_name,
            region=region,
        )

        self.assertEqual(credentials.role_arn, role_arn)
        self.assertEqual(credentials.web_identity_provider, web_identity_provider)
        self.assertEqual(credentials.role_session_name, role_session_name)
        self.assertEqual(credentials.region, region)
