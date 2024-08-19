import hashlib
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Type
from uuid import uuid4
import uuid

from fastapi import Request
from pydantic import BaseModel

from faster_sam.protocols import IntoSQSInfo


async def apigateway_proxy(request: Request) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    body = await request.body()
    event = {
        "body": body.decode(),
        "path": request.url.path,
        "httpMethod": request.method,
        "isBase64Encoded": False,
        "queryStringParameters": dict(request.query_params),
        "pathParameters": dict(request.path_params),
        "headers": dict(request.headers),
        "requestContext": {
            "stage": request.app.version,
            "requestId": str(uuid4()),
            "requestTime": now.strftime(r"%d/%b/%Y:%H:%M:%S %z"),
            "requestTimeEpoch": int(now.timestamp()),
            "identity": {
                "sourceIp": getattr(request.client, "host", None),
                "userAgent": request.headers.get("user-agent"),
            },
            "path": request.url.path,
            "httpMethod": request.method,
            "protocol": f"HTTP/{request.scope['http_version']}",
        },
    }
    return event


def sqs(schema: Type[BaseModel]) -> Callable[[BaseModel], Dict[str, Any]]:
    def dep(message: schema) -> Dict[str, Any]:
        assert isinstance(message, IntoSQSInfo)

        info = message.into()
        event = {
            "Records": [
                {
                    "messageId": info.id,
                    "receiptHandle": str(uuid.uuid4()),
                    "body": info.body,
                    "attributes": {
                        "ApproximateReceiveCount": info.receive_count,
                        "SentTimestamp": info.sent_timestamp,
                        "SenderId": str(uuid.uuid4()),
                        "ApproximateFirstReceiveTimestamp": info.sent_timestamp,
                    },
                    "messageAttributes": info.message_attributes,
                    "md5OfBody": hashlib.md5(info.body.encode()).hexdigest(),
                    "eventSource": "aws:sqs",
                    "eventSourceARN": info.source_arn,
                    "awsRegion": None,
                },
            ]
        }

        return event

    return dep
