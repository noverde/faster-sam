import base64
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import uuid

from fastapi import FastAPI, Request

from faster_sam.dependencies import events
from faster_sam.schemas import PubSubEnvelope


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


def build_request_bucket():
    async def receive():
        body = {
            "kind": "storage#object",
            "id": "test-bucket/my-object/171355802",
            "selfLink": "https://www.googleapis.com/storage/v1/b/test-bucket/o/my-object",
            "name": "my-object",
            "bucket": "test-bucket",
            "generation": "17135544002",
            "metageneration": "1",
            "contentType": "image/png",
            "timeCreated": "2024-04-19T19:20:02.583Z",
            "updated": "2024-04-19T19:20:02.583Z",
            "storageClass": "STANDARD",
            "timeStorageClassUpdated": "2024-04-19T19:20:02.583Z",
            "size": 1234,
            "md5Hash": "VZsw8CMPjh427rA==",
            "mediaLink": "https://storage.googleapis.com/download/storage/v1/b/test-bucket",
            "crc32c": "EIMw==",
            "etag": "CMKy4UDEAE=",
        }
        return {"type": "http.request", "body": json.dumps(body).encode()}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "root_path": "/s3event",
        "path": "/test-bucket",
        "method": "POST",
        "query_string": b"",
        "headers": {
            b"x-forwarded-for": b"192.178.13.229",
            b"ce-id": b"9475010998622634",
            b"ce-time": b"2024-04-19T21:01:59.503551Z",
            b"ce-bucket": b"test-bucket",
        },
        "client": ("169.254.1.1", 35668),
        "server": ("192.168.1.1", 8080),
        "scheme": "http",
        "app": FastAPI(),
    }

    return Request(scope, receive)


class TestS3Event(unittest.IsolatedAsyncioTestCase):
    async def test_s3_event(self):
        request = build_request_bucket()
        sequencer = uuid.uuid4()
        with patch("uuid.uuid4", return_value=sequencer):
            event = await events.s3(request)

        self.assertIsInstance(event, dict)
        self.assertIn("Records", event)
        self.assertEqual(len(event["Records"]), 1)
        record = event["Records"][0]
        self.assertEqual(record["eventSource"], "aws:s3")
        self.assertEqual(record["eventName"], "s3:ObjectCreated:*")
        self.assertEqual(record["s3"]["bucket"]["name"], "test-bucket")
        self.assertEqual(record["s3"]["object"]["key"], "my-object")
        self.assertEqual(record["s3"]["object"]["size"], 1234)
        self.assertEqual(record["s3"]["object"]["eTag"], "CMKy4UDEAE=")
        self.assertEqual(record["s3"]["s3SchemaVersion"], "1.0")
        self.assertIn("sequencer", record["s3"]["object"])
        self.assertEqual(record["s3"]["object"]["sequencer"], int(sequencer))
