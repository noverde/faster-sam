import base64
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict
from uuid import uuid4

from fastapi import Request, Response

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]


class CustomResponse(Response):
    """
    Represents an API Gateway HTTP response.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initializes the ApiGatewayResponse.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary containing the response data.
        """

        super().__init__(
            content=data["body"],
            status_code=data["statusCode"],
            headers=data.get("headers"),
            media_type=data.get("headers", {}).get("Content-Type"),
        )


class ResourceInterface(ABC):
    @abstractmethod
    def __init__(self, request: Request, endpoint: Handler):
        self.request = request
        self.endpoint = endpoint

    @abstractmethod
    async def call_endpoint(self) -> Response:
        pass  # pragma: no cover

    @abstractmethod
    async def event_builder(self, request: Request) -> Dict[str, Any]:
        pass  # pragma: no cover


class SQS(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        event = await self.event_builder()
        try:
            result = self.endpoint(event, None)
        except Exception:
            return CustomResponse({"body": "Error processing message", "statusCode": 500})

        if "batchItemFailures" in result:
            return CustomResponse({"body": json.dumps(result), "statusCode": 500})

        return CustomResponse({"body": json.dumps(result), "statusCode": 200})

    async def event_builder(self):
        bytes_body = await self.request.body()
        json_body = bytes_body.decode()
        body = json.loads(json_body)

        attributes = {
            "ApproximateReceiveCount": body["deliveryAttempt"],
            "SentTimestamp": datetime.timestamp(
                datetime.strptime(body["message"]["publishTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
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
                    "md5OfBody": hashlib.md5(json_body.encode("utf-8")).hexdigest(),
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
                    "awsRegion": "us-east-2",
                },
            ]
        }
        return event


class ApiGateway(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        event = await self.event_builder()
        result = self.endpoint(event, None)
        response = CustomResponse(result)

        return response

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
