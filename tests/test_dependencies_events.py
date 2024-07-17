import unittest

from fastapi import FastAPI, Request

from faster_sam.dependencies import events


def build_request():
    async def receive():
        return {"type": "http.request", "body": b'{"message": "pong"}'}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "root_path": "",
        "path": "/ping/pong",
        "method": "GET",
        "query_string": b"q=all&skip=100",
        "path_params": {"message": "pong"},
        "client": ("127.0.0.1", 80),
        "app": FastAPI(),
        "headers": [
            (b"content-type", b"application/json"),
            (b"user-agent", b"python/unittest"),
        ],
    }

    return Request(scope, receive)


class TestApiGatewayProxy(unittest.IsolatedAsyncioTestCase):
    async def test_event(self):
        request = build_request()
        event = await events.apigateway_proxy(request)

        self.assertIsInstance(event, dict)
        self.assertEqual(event["body"], '{"message": "pong"}')
        self.assertEqual(event["path"], "/ping/pong")
        self.assertEqual(event["httpMethod"], "GET")
        self.assertEqual(event["isBase64Encoded"], False)
        self.assertEqual(event["queryStringParameters"], {"q": "all", "skip": "100"})
        self.assertEqual(event["pathParameters"], {"message": "pong"})
        self.assertEqual(
            event["headers"],
            {"content-type": "application/json", "user-agent": "python/unittest"},
        )
        self.assertEqual(event["requestContext"]["stage"], "0.1.0")
        self.assertEqual(event["requestContext"]["identity"]["sourceIp"], "127.0.0.1")
        self.assertEqual(event["requestContext"]["identity"]["userAgent"], "python/unittest")
        self.assertEqual(event["requestContext"]["path"], "/ping/pong")
        self.assertEqual(event["requestContext"]["httpMethod"], "GET")
        self.assertEqual(event["requestContext"]["protocol"], "HTTP/1.1")
