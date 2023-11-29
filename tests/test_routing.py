import copy
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request, Response

import routing


class TestAPIRoute(unittest.TestCase):
    def test_default_endpoint(self):
        with self.assertLogs(logger=routing.__name__, level="ERROR") as logs:
            scope = {"type": "http"}
            request = Request(scope)
            response = routing.default_endpoint(request)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(response.media_type, "application/json")
        self.assertEqual(response.body, b'{"error": "Invalid endpoint execution"}')

        expected_logs = ["ERROR:routing:Executing default endpoint: {'type': 'http'}"]
        self.assertEqual(logs.output, expected_logs)

    def test_route(self):
        def handler(event, context):
            print(f"event: {event}\ncontext: {context}")
            return {"statusCode": 200, "body": ""}

        route = routing.APIRoute(path="/test", name="test", lambda_handler=handler)

        self.assertEqual(route.path, "/test")
        self.assertEqual(route.name, "test")
        self.assertEqual(route.methods, {"GET"})
        self.assertIsInstance(route.endpoint, routing.default_endpoint.__class__)
        self.assertIsInstance(route.lambda_handler, handler.__class__)


class TestImportHandler(unittest.TestCase):
    def test_import_handler(self):
        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"

        handler = routing.import_handler(handler_path)

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
        response = routing.ApiGatewayResponse(self.data)

        self.assertEqual(response.status_code, self.data["statusCode"])
        self.assertEqual(response.body.decode(), self.data["body"])
        self.assertEqual(response.headers["content-type"], self.data["headers"]["content-type"])

    def test_response_creation_fails_when_missing_required_attribute(self):
        for attr in self.data.keys():
            with self.subTest(attribute=attr):
                data = copy.deepcopy(self.data)
                del data[attr]

                with self.assertRaises(KeyError):
                    routing.ApiGatewayResponse(data)


class TestEventBuilder(unittest.IsolatedAsyncioTestCase):
    async def test_event_builder(self):
        async def receive():
            return {"type": "http.request", "body": b'{"message":  "test"}'}

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
        }
        request = Request(scope, receive)
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

        event = await routing.event_builder(request)

        self.assertIsInstance(event, dict)
        self.assertEqual(set(event.keys()), expected_keys)
