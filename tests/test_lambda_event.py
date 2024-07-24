import copy
import json
import unittest
from http import HTTPStatus

from fastapi import FastAPI, Request

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


def build_request_sqs_with_milliseconds():
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


def build_request_sqs_with_seconds():
    async def receive():
        body = {
            "deliveryAttempt": 1,
            "message": {
                "attributes": {"endpoint": "sre-tests-queue"},
                "data": "aGVsbG8=",
                "messageId": "10519041647717348",
                "message_id": "10519041647717348",
                "publishTime": "2024-02-22T15:45:31Z",
                "publish_time": "2024-02-22T15:45:31Z",
            },
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


def build_request_schedule():

    async def receive():
        body = {}
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


def build_request_bucket():
    async def receive():
        body = {
            "kind": "storage#object",
            "id": "test-bucket/Captura.png/171355802",
            "selfLink": "https://www.googleapis.com/storage/v1/b/test-bucket/o/Captura.png",
            "name": "Captura.png",
            "bucket": "test-bucket",
            "generation": "17135544002",
            "metageneration": "1",
            "contentType": "image/png",
            "timeCreated": "2024-04-19T19:20:02.583Z",
            "updated": "2024-04-19T19:20:02.583Z",
            "storageClass": "STANDARD",
            "timeStorageClassUpdated": "2024-04-19T19:20:02.583Z",
            "size": "21032",
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


class TestCustomResponse(unittest.TestCase):
    def setUp(self):
        self.data = {
            "statusCode": HTTPStatus.OK.value,
            "body": '{"message": "test"}',
            "headers": {"content-type": "application/json"},
        }

    def test_response_creation(self):
        response = faster_sam.lambda_event.CustomResponse(self.data)

        self.assertEqual(response.status_code, self.data["statusCode"])
        self.assertEqual(response.body.decode(), self.data["body"])
        self.assertEqual(response.headers["content-type"], self.data["headers"]["content-type"])

    def test_response_creation_fails_when_missing_required_attribute(self):
        for attr in ("statusCode", "body"):
            with self.subTest(attribute=attr):
                data = copy.deepcopy(self.data)
                del data[attr]

                with self.assertRaises(KeyError):
                    faster_sam.lambda_event.CustomResponse(data)


class TestEventBuilder(unittest.IsolatedAsyncioTestCase):
    async def test_event_builder_api(self):
        request = build_request_api_gateway()
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

        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"
        handler = faster_sam.routing.import_handler(handler_path)

        api_gateway = faster_sam.lambda_event.ApiGateway(request, handler)

        event = await api_gateway.event_builder()

        self.assertIsInstance(event, dict)
        self.assertEqual(set(event.keys()), expected_keys)
        self.assertIn("authorizer", event["requestContext"])

    async def test_event_builder_sqs(self):
        expected_key = {
            "messageId",
            "receiptHandle",
            "body",
            "attributes",
            "messageAttributes",
            "md5OfBody",
            "eventSource",
            "eventSourceARN",
            "awsRegion",
        }

        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"
        handler = faster_sam.routing.import_handler(handler_path)

        cases = {
            "publish_time_with_milliseconds": build_request_sqs_with_milliseconds,
            "publish_time_with_seconds": build_request_sqs_with_seconds,
        }

        for case, request in cases.items():
            with self.subTest(case=case):
                sqs = faster_sam.lambda_event.SQS(request(), handler)

                event = await sqs.event_builder()

                self.assertIsInstance(event, dict)
                self.assertEqual(set(event["Records"][0].keys()), expected_key)

    async def test_event_builder_schedule(self):
        request = build_request_schedule()
        expected_keys = {
            "version",
            "id",
            "detail-type",
            "source",
            "account",
            "time",
            "region",
            "resources",
            "detail",
        }

        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"
        handler = faster_sam.routing.import_handler(handler_path)

        schedule = faster_sam.lambda_event.Schedule(request, handler)

        event = await schedule.event_builder()

        self.assertIsInstance(event, dict)
        self.assertEqual(set(event.keys()), expected_keys)

    async def test_event_builder_bucket(self):
        request = build_request_bucket()
        expected_keys = {
            "requestParameters",
            "s3",
            "eventTime",
            "userIdentity",
            "eventName",
            "responseElements",
            "awsRegion",
            "eventVersion",
            "eventSource",
        }

        module_name = "tests.fixtures.handlers.lambda_handler"
        handler_name = "handler"
        handler_path = f"{module_name}.{handler_name}"
        handler = faster_sam.routing.import_handler(handler_path)

        bucket = faster_sam.lambda_event.Bucket(request, handler)

        event = await bucket.event_builder()

        self.assertIsInstance(event, dict)
        print(set(event["Records"][0].keys()))
        self.assertEqual(set(event["Records"][0].keys()), expected_keys)
