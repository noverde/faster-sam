import base64
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import Response

from faster_sam.responses import ApiGatewayResponse, SQSResponse


class LambdaTriggerInterface(ABC):
    @abstractmethod
    def call_endpoint(self) -> Dict[str, Any]:
        pass


class ApiGatewayTrigger(LambdaTriggerInterface):
    def __init__(self, request, endpoint: str):
        self.request = request
        self.func = endpoint

    async def event_builder(self) -> Dict[str, Any]:
        """
        Builds an event of type aws_proxy from API Gateway.

        It uses the given request object to fill the event details.

        Parameters
        ----------
        request : Request
            A request object.

        Returns
        -------
        Dict[str, Any]
            An aws_proxy event.
        """

        now = datetime.now(timezone.utc)
        body = await self.request.body()
        event = {
            "body": body.decode(),
            "path": self.request.url.path,
            "httpMethod": self.request.method,
            "isBase64Encoded": False,
            "queryStringParameters": dict(self.request.query_params),
            "pathParameters": dict(self.request.path_params),
            "headers": dict(self.request.headers),
            "requestContext": {
                "stage": self.request.app.version,
                "requestId": str(uuid4()),
                "requestTime": now.strftime(r"%d/%b/%Y:%H:%M:%S %z"),
                "requestTimeEpoch": int(now.timestamp()),
                "identity": {
                    "sourceIp": getattr(self.request.client, "host", None),
                    "userAgent": self.request.headers.get("user-agent"),
                },
                "path": self.request.url.path,
                "httpMethod": self.request.method,
                "protocol": f"HTTP/{self.request.scope['http_version']}",
                "authorizer": self.request.scope.get("authorization_context"),
            },
        }

        return event

    async def call_endpoint(self) -> Response:
        event = await self.event_builder()
        response = self.func(event, None)
        return ApiGatewayResponse(response)


class SQSTrigger(LambdaTriggerInterface):
    def __init__(self, request, endpoint: str):
        self.request = request
        self.func = endpoint

    async def event_builder(self) -> Dict[str, Any]:
        body = await self.request.body()
        body = json.loads(body.decode())

        attributes = {
            "ApproximateReceiveCount": body["deliveryAttempt"],
            "SentTimestamp": datetime.timestamp(
                datetime.fromisoformat(body["message"]["publishTime"])
            )
            * 1000.0,
            "SenderId": "",
            "ApproximateFirstReceiveTimestamp": "",
        }

        event = {
            "Records": [
                {
                    "messageId": body["message"]["messageId"],
                    "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a...",
                    "body": base64.b64decode(body["message"]["data"]).decode("UTF-8"),
                    "attributes": attributes,
                    "messageAttributes": body["message"]["attributes"],
                    "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
                    "awsRegion": "us-east-2",
                },
            ]
        }
        return event

    async def call_endpoint(self) -> Response:
        status_code = 200
        message = None
        result = None
        try:
            event = await self.event_builder()
            result = self.func(event, None)
        except Exception:
            status_code = 500
            message = "Something went wrong"

        if result is not None:
            message = result

        return SQSResponse(content=json.dumps(message), status_code=status_code)
