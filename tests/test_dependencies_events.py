import base64
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import uuid
import json

from fastapi import FastAPI, Request

from faster_sam.dependencies import events
from faster_sam.schemas import PubSubEnvelope
from typing import Dict, Any


def build_request(path: str, response=Dict[str, Any], method: str = "GET"):
    async def receive():
        return response

    scope = {
        "type": "http",
        "http_version": "1.1",
        "root_path": "",
        "path": path,
        "method": method,
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
        path = "/ping/pong"
        response = {"type": "http.request", "body": b'{"message": "pong"}'}
        request = build_request(path, response)
        event = await events.apigateway_proxy(request)

        self.assertIsInstance(event, dict)
        self.assertEqual(event["body"], response["body"].decode())
        self.assertEqual(event["path"], path)
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


class TestSQS(unittest.TestCase):
    async def test_event(self):
        data = {
            "message": {
                "data": "aGVsbG8=",
                "attributes": {"foo": "bar"},
                "messageId": "10519041647717348",
                "publishTime": "2024-02-22T15:45:31.346Z",
            },
            "subscription": "projects/foo/subscriptions/bar",
            "deliveryAttempt": 1,
        }

        pubsub_envelope = PubSubEnvelope(**data)

        sender_id = uuid.uuid4()

        with patch("uuid.uuid4", return_value=sender_id):
            SQSEvent = events.sqs(PubSubEnvelope)

        event = SQSEvent(pubsub_envelope)

        parsed_datetime = datetime.strptime(data["message"]["publishTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
        parsed_datetime_utc = parsed_datetime.replace(tzinfo=timezone.utc)
        timestamp_milliseconds = int(parsed_datetime_utc.timestamp() * 1000)

        self.assertIsInstance(event, dict)
        record = event["Records"][0]
        self.assertEqual(record["messageId"], data["message"]["messageId"])
        self.assertEqual(record["body"], base64.b64decode(data["message"]["data"]).decode("utf-8"))
        self.assertEqual(record["attributes"]["ApproximateReceiveCount"], data["deliveryAttempt"])
        self.assertEqual(
            record["attributes"]["SentTimestamp"],
            timestamp_milliseconds,
        )
        self.assertEqual(record["attributes"]["SenderId"], str(sender_id))
        self.assertEqual(
            record["attributes"]["ApproximateFirstReceiveTimestamp"],
            timestamp_milliseconds,
        )
        self.assertEqual(record["messageAttributes"], data["message"]["attributes"])
        self.assertEqual(
            record["md5OfBody"],
            data["message"]["data"],
        )
        self.assertEqual(record["eventSource"], "aws:sqs")
        self.assertEqual(
            record["eventSourceARN"],
            f"arn:aws:sqs:::{data['subscription'].rsplit('/', maxsplit=1)[-1]}",
        )


class TestS3Event(unittest.IsolatedAsyncioTestCase):
    async def test_s3_event(self):
        path = "/test-bucket"
        body = {
            "name": "my-object",
            "bucket": "test-bucket",
            "timeCreated": "2024-04-19T19:20:02.583Z",
            "size": 1234,
            "etag": "CMKy4UDEAE=",
        }
        response = {"type": "http.request", "body": json.dumps(body).encode()}
        method = "POST"
        request = build_request(path, response, method)
        sequencer = uuid.uuid4()
        with patch("uuid.uuid4", return_value=sequencer):
            event = await events.s3(request)

        self.assertIsInstance(event, dict)
        self.assertIn("Records", event)
        self.assertEqual(len(event["Records"]), 1)
        record = event["Records"][0]
        self.assertEqual(record["s3"]["bucket"]["name"], "test-bucket")
        self.assertEqual(record["s3"]["object"]["key"], "my-object")
        self.assertEqual(record["s3"]["object"]["size"], 1234)
        self.assertEqual(record["s3"]["object"]["eTag"], "CMKy4UDEAE=")
        self.assertEqual(record["s3"]["object"]["sequencer"], int(sequencer))
