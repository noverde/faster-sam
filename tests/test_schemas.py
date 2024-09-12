import unittest
import base64
from datetime import datetime, timezone

from faster_sam import schemas


class TestPubSubEnvelope(unittest.TestCase):
    def setUp(self):
        self.data = {
            "message": {
                "data": "eyJmb28iOiAiYmFyIn0=",
                "messageId": "12132665510234298",
                "publishTime": "2024-09-06T19:24:19.609Z",
                "attributes": {"foo": "bar"},
            },
            "subscription": "projects/test/subscriptions/test",
            "deliveryAttempt": 1,
        }

    def test_with_complete_input_data(self):
        msg = base64.b64decode(self.data["message"]["data"]).decode()
        dt = datetime.strptime(self.data["message"]["publishTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
        dt = dt.replace(tzinfo=timezone.utc)

        envelope = schemas.PubSubEnvelope(**self.data)

        self.assertEqual(envelope.message.data, msg)
        self.assertEqual(envelope.message.messageId, self.data["message"]["messageId"])
        self.assertEqual(envelope.message.publishTime, dt)
        self.assertEqual(envelope.message.attributes, self.data["message"]["attributes"])
        self.assertEqual(envelope.subscription, self.data["subscription"])
        self.assertEqual(envelope.deliveryAttempt, self.data["deliveryAttempt"])

    def test_without_delivery_attempt(self):
        del self.data["deliveryAttempt"]

        envelope = schemas.PubSubEnvelope(**self.data)

        self.assertEqual(envelope.deliveryAttempt, 0)

    def test_without_message_attributes(self):
        del self.data["message"]["attributes"]

        envelope = schemas.PubSubEnvelope(**self.data)

        self.assertEqual(envelope.message.attributes, None)

    def test_into(self):
        envelope = schemas.PubSubEnvelope(**self.data)
        sqs_info = envelope.into()

        self.assertIsInstance(sqs_info, schemas.SQSInfo)
