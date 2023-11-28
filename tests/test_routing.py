import unittest
from http import HTTPStatus

from fastapi import Request, Response

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
