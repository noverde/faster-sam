from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Base64UrlStr, Field


class SQSInfo(BaseModel):
    id: str
    body: str
    receive_count: int
    sent_timestamp: int
    source_arn: str
    message_attributes: Optional[Dict[str, str]] = Field(default=None)


class PubSubMessage(BaseModel):
    data: Base64UrlStr
    messageId: str
    publishTime: datetime
    attributes: Optional[Dict[str, str]] = Field(default=None)


class PubSubEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str
    deliveryAttempt: int

    def into(self) -> SQSInfo:
        milliseconds = 1000

        publish_time = int(self.message.publishTime.timestamp() * milliseconds)

        topic_name = self.subscription.rsplit("/", maxsplit=1)[-1]
        source_arn = f"arn:aws:sqs:::{topic_name}"
        return SQSInfo(
            id=self.message.messageId,
            body=self.message.data,
            receive_count=self.deliveryAttempt,
            sent_timestamp=publish_time,
            message_attributes=self.message.attributes,
            source_arn=source_arn,
        )
