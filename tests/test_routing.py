import copy
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request, Response

import faster_sam.routing


def build_request():
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


class TestApiGatewayResponse(unittest.TestCase):
    def setUp(self):
        self.data = {
            "statusCode": HTTPStatus.OK.value,
            "body": '{"message": "test"}',
            "headers": {"content-type": "application/json"},
        }

    def test_response_creation(self):
        response = faster_sam.routing.ApiGatewayResponse(self.data)

        self.assertEqual(response.status_code, self.data["statusCode"])
        self.assertEqual(response.body.decode(), self.data["body"])
        self.assertEqual(response.headers["content-type"], self.data["headers"]["content-type"])

    def test_response_creation_fails_when_missing_required_attribute(self):
        for attr in ("statusCode", "body"):
            with self.subTest(attribute=attr):
                data = copy.deepcopy(self.data)
                del data[attr]

                with self.assertRaises(KeyError):
                    faster_sam.routing.ApiGatewayResponse(data)


class TestEventBuilder(unittest.IsolatedAsyncioTestCase):
    async def test_event_builder(self):
        request = build_request()
        expected_keys = {
            "body",
            "path",
            "httpMethod",
            "isBase64Encoded",
            "queryStringParameters",
            "pathParameters",
            "headers",
            "requestContext",
        }

        event = await faster_sam.routing.event_builder(request)

        self.assertIsInstance(event, dict)
        self.assertEqual(set(event.keys()), expected_keys)
        self.assertIn("authorizer", event["requestContext"])


class TestHandler(unittest.IsolatedAsyncioTestCase):
    async def test_handler(self):
        request = build_request()

        def echo(event, _):
            return {
                "statusCode": HTTPStatus.OK.value,
                "body": event["body"],
                "headers": event["headers"],
            }

        endpoint = faster_sam.routing.handler(echo)
        response = await endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        self.assertEqual(response.body.decode(), '{"message": "test"}')
        self.assertEqual(response.headers["content-type"], "application/json")
