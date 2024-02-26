import json
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request, Response

import faster_sam.lambda_event
import faster_sam.routing


def build_request_api_gateway():
    async def receive():
        return {"type": "http.request", "body": b'{"message": "test"}'}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "root_path": "",
        "path": "/test",
        "method": "GET",
        "query_string": [],
        "path_params": {},
        "client": ("127.0.0.1", 80),
        "app": FastAPI(),
        "headers": [
            (b"content-type", b"application/json"),
            (b"user-agent", b"python/unittest"),
        ],
        "authorization_context": {
            "borrower_id": 1,
            "cpf": "07491376819",
            "sid": "e6be99e7-a103-4394-95e8-b5bf1c7294da",
            "user_uuid": "53d13ce4-f6d6-453e-895e-db02b486d6f7",
        },
    }

    return Request(scope, receive)


def build_request_sqs():
    async def receive():
        body = {
            "deliveryAttempt": 1,
            "message": {
                "attributes": {"endpoint": "sre-tests-queue"},
                "data": "aGVsbG8=",
                "messageId": "10519041647717348",
                "message_id": "10519041647717348",
                "publishTime": "2024-02-22T15:45:31.346Z",
                "publish_time": "2024-02-22T15:45:31.346Z",
            },
            "subscription": "projects/dotz-noverde-dev/subscriptions/test-workflows",
        }
        return {"type": "http.request", "body": json.dumps(body).encode()}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "root_path": "",
        "path": "/test",
        "method": "GET",
        "query_string": [],
        "path_params": {},
        "client": ("127.0.0.1", 80),
        "app": FastAPI(),
    }

    return Request(scope, receive)


class TestAPIRoute(unittest.TestCase):
    def test_route(self):
        endpoint = "tests.fixtures.handlers.lambda_handler.handler"

        route = faster_sam.routing.APIRoute(path="/test", name="test", endpoint=endpoint)

        self.assertEqual(route.path, "/test")
        self.assertEqual(route.name, "test")
        self.assertEqual(route.methods, {"GET"})
        self.assertTrue(callable(route.endpoint))


class TestImportHandler(unittest.TestCase):
    def test_import_handler(self):
        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"

        handler = faster_sam.routing.import_handler(handler_path)

        self.assertTrue(callable(handler))
        self.assertEqual(getattr(handler, "__module__", None), module_name)
        self.assertEqual(getattr(handler, "__name__", None), handler_name)


class TestHandler(unittest.IsolatedAsyncioTestCase):
    async def test_api_gateway_handler(self):
        request = build_request_api_gateway()

        def echo(event, _):
            return {
                "statusCode": HTTPStatus.OK.value,
                "body": event["body"],
                "headers": event["headers"],
            }

        endpoint = faster_sam.routing.handler(echo, faster_sam.lambda_event.ApiGateway)
        response = await endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        self.assertEqual(response.body.decode(), '{"message": "test"}')
        self.assertEqual(response.headers["content-type"], "application/json")

    async def test_sqs_handler(self):
        request = build_request_sqs()

        def echo(event, _):
            return {
                "statusCode": HTTPStatus.OK.value,
                "body": event["Records"][0]["body"],
            }

        endpoint = faster_sam.routing.handler(echo, faster_sam.lambda_event.SQS)
        response = await endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        self.assertEqual(response.body.decode(), '{"statusCode": 200, "body": "hello"}')

    async def test_sqs_handler_exception(self):
        request = build_request_sqs()

        def echo():
            return None

        endpoint = faster_sam.routing.handler(echo, faster_sam.lambda_event.SQS)
        response = await endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.value)
        self.assertEqual(response.body.decode(), "Error processing message")

    async def test_sqs_handler_failed(self):
        request = build_request_sqs()

        def echo(event, _):
            return {
                "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value,
                "body": event["Records"][0]["body"],
                "batchItemFailures": "foo",
            }

        endpoint = faster_sam.routing.handler(echo, faster_sam.lambda_event.SQS)
        response = await endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR.value)
        self.assertEqual(
            response.body.decode(),
            '{"statusCode": 500, "body": "hello", "batchItemFailures": "foo"}',
        )
