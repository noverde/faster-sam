import base64
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict
from uuid import uuid4

from fastapi import BackgroundTasks, Request, Response

logger = logging.getLogger(__name__)

KILO_SECONDS = 1000.0

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]


class CustomResponse(Response):
    """
    Represents an HTTP response.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initializes the Custom Response.

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
            background=data.get("background_tasks"),
        )


class ResourceInterface(ABC):
    """
    Interface for aws resources.

    This abstract base class defines an interface for aws resources
    to implement. Subclasses must implement the `call_endpoint` and
    `event_builder` methods to map events.
    """

    @abstractmethod
    def __init__(self, request: Request, endpoint: Handler):
        """
        Initializes the Resource Interface.

        Parameters
        ----------
        request : Request
            A request object.
        endpoint : Handler
            A callable object.
        """
        self.request = request
        self.endpoint = endpoint

    @abstractmethod
    async def call_endpoint(self) -> Response:
        """
        Call event buider and retuns a custom response based
        on the mapped event.

        Returns
        -------
        Response
            A response object.
        """
        pass  # pragma: no cover

    @abstractmethod
    async def event_builder(self) -> Dict[str, Any]:
        """
        Builds an event based on the current request.

        Returns
        -------
        Dict[str, Any]
            The mapped event.
        """
        pass  # pragma: no cover


class SQS(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        """
        Initializes the SQS.

        Parameters
        ----------
        request : Request
            A request object.
        endpoint : Handler
            A callable object.
        """
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        """
        Call event buider and retuns a custom response based
        on the mapped event.

        Returns
        -------
        Response
            A response object.
        """
        event = await self.event_builder()
        try:
            result = self.endpoint(event, None)
        except Exception as error:
            logger.exception(error)
            return CustomResponse({"body": "Error processing message", "statusCode": 500})

        if isinstance(result, dict) and "batchItemFailures" in result:
            return CustomResponse({"body": json.dumps(result), "statusCode": 500})

        return CustomResponse({"body": json.dumps(result), "statusCode": 200})

    async def event_builder(self):
        """
        Builds an event of type sqs

        It uses the given request object to fill the event details.

        Returns
        -------
        Dict[str, Any]
            An sqs event.
        """
        bytes_body = await self.request.body()
        json_body = bytes_body.decode()
        body = json.loads(json_body)

        attributes = {
            "ApproximateReceiveCount": body["deliveryAttempt"],
            "SentTimestamp": datetime.timestamp(
                datetime.strptime(body["message"]["publishTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
            )
            * KILO_SECONDS,
            "SenderId": "",
            "ApproximateFirstReceiveTimestamp": "",
        }

        logger.warning(f"Message Attributes: {body['message'].get('attributes', '')}")

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


class Schedule(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        """
        Initializes the Schedule.

        Parameters
        ----------
        request : Request
            A request object.
        endpoint : Handler
            A callable object.
        """
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        """
        Call event buider and retuns a custom response based
        on the mapped event.

        Returns
        -------
        Response
            A response object.
        """
        event = await self.event_builder()

        tasks = BackgroundTasks()

        tasks.add_task(self.endpoint, event, None)

        return CustomResponse(
            {
                "body": json.dumps({"message": "send for processing"}),
                "statusCode": 202,
                "background_tasks": tasks,
            }
        )

    async def event_builder(self):
        """
        Builds an event of type schedule

        It uses the given request object to fill the event details.

        Returns
        -------
        Dict[str, Any]
            An schedule event.
        """

        bytes_body = await self.request.body()
        json_body = bytes_body.decode()
        body = json.loads(json_body)
        event = {
            "version": "0",
            "id": str(uuid4()),
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "account": "",
            "time": datetime.now(timezone.utc).strftime(r"%d/%b/%Y:%H:%M:%S %z"),
            "region": "us-east-1",
            "resources": [""],
            "detail": body,
        }

        return event


class Bucket(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        """
        Initializes the Bucket.

        Parameters
        ----------
        request : Request
            A request object.
        endpoint : Handler
            A callable object.
        """
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        """
        Call event buider and retuns a custom response based
        on the mapped event.

        Returns
        -------
        Response
            A response object.
        """
        event = await self.event_builder()

        try:
            result = self.endpoint(event, None)
        except Exception as error:
            logger.exception(error)
            return CustomResponse({"body": "Error processing request", "statusCode": 500})

        return CustomResponse({"body": json.dumps(result), "statusCode": 200})

    async def event_builder(self):
        """
        Builds an event of type bucket

        It uses the given request object to fill the event details.

        Returns
        -------
        Dict[str, Any]
            An bucket event.
        """
        bytes_body = await self.request.body()
        json_body = bytes_body.decode()
        body = json.loads(json_body)

        event = {
            "Records": [
                {
                    "eventVersion": "2.0",
                    "eventSource": "aws:s3",
                    "awsRegion": "us-east-1",
                    "eventTime": body["timeCreated"],
                    "eventName": "s3:ObjectCreated:*",
                    "userIdentity": {"principalId": ""},
                    "requestParameters": {"sourceIPAddress": ""},
                    "responseElements": {
                        "x-amz-request-id": "",
                        "x-amz-id-2": "EXAMPLE123/",
                    },
                    "s3": {
                        "s3SchemaVersion": "1.0",
                        "configurationId": "testConfigRule",
                        "bucket": {
                            "name": body["bucket"],
                            "ownerIdentity": {"principalId": "EXAMPLE"},
                            "arn": "arn:aws:s3:::example-bucket",
                        },
                        "object": {
                            "key": body["name"],
                            "size": body["size"],
                            "eTag": body["etag"],
                            "sequencer": "",
                        },
                    },
                }
            ]
        }

        return event


class ApiGateway(ResourceInterface):
    def __init__(self, request: Request, endpoint: Handler):
        """
        Initializes the ApiGateway.

        Parameters
        ----------
        request : Request
            A request object.
        endpoint : Handler
            A callable object.
        """
        super().__init__(request, endpoint)

    async def call_endpoint(self) -> Response:
        """
        Call event buider and retuns a custom response based
        on the mapped event.

        Returns
        -------
        Response
            A response object.
        """
        event = await self.event_builder()
        result = self.endpoint(event, None)
        response = CustomResponse(result)

        return response

    async def event_builder(self) -> Dict[str, Any]:
        """
        Builds an event of type aws_proxy from API Gateway.

        It uses the given request object to fill the event details.

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
