import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI

from faster_sam.adapter import SAM, GatewayLookupError
from faster_sam.cloudformation import CloudformationTemplate


class TestSAM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = (
            "tests/fixtures/templates/example1.yml",
            "tests/fixtures/templates/example2.yml",
            "tests/fixtures/templates/example3.yml",
            "tests/fixtures/templates/example4.yml",
            "tests/fixtures/templates/example5.yml",
        )

    def test_initialization(self):
        for template in self.templates:
            with self.subTest(template=template):
                sam = SAM(template)

                self.assertIsInstance(sam, SAM)
                self.assertIsInstance(sam.template, CloudformationTemplate)

    def test_environment_initialization(self):
        SAM(
            "tests/fixtures/templates/example2.yml",
            parameters={"Environment": "development"},
        )

        self.assertEqual(os.environ.get("ENVIRONMENT"), "development")
        self.assertEqual(os.environ.get("LOG_LEVEL"), "DEBUG")

    def test_configure_api(self):
        gateways = (None, None, "ApiGateway", "ApiGatewayTwo", None)
        routes = (5, 5, 5, 6, 6)

        for template, gateway, expected_routes in zip(self.templates, gateways, routes):
            with self.subTest(template=template, gateway=gateway):
                app = FastAPI()
                sam = SAM(template)

                self.assertEqual(len(app.routes), 4)

                sam.configure_api(app, gateway)

                self.assertEqual(len(app.routes), expected_routes)

    def test_configure_multiple_apis(self):
        app = FastAPI()
        subapp = FastAPI()
        app.mount("/subapp", subapp)

        sam = SAM(self.templates[3])
        sam.configure_api(app, "ApiGateway")
        sam.configure_api(subapp, "ApiGatewayTwo")

        self.assertEqual(len(app.routes), 6)
        self.assertEqual(len(subapp.routes), 6)

    def test_configure_queues(self):
        app = FastAPI()
        sam = SAM("tests/fixtures/templates/example6.yml")

        self.assertEqual(len(app.routes), 4)

        sam.configure_queues(app)
        self.assertEqual(len(app.routes), 5)

    def test_configure_schedule(self):
        app = FastAPI()
        sam = SAM("tests/fixtures/templates/example7.yml")

        self.assertEqual(len(app.routes), 4)

        sam.configure_schedule(app)
        self.assertEqual(len(app.routes), 5)

    @patch.dict(
        "os.environ",
        {
            "PROJECT_NUMBER": "123",
        },
    )
    def test_configure_bucket(self):
        app = FastAPI()
        sam = SAM("tests/fixtures/templates/example7.yml")

        self.assertEqual(len(app.routes), 4)

        sam.configure_bucket(app)
        self.assertEqual(len(app.routes), 5)

    def test_configure_api_raises_gateway_lookup_error(self):
        error = "^Missing required gateway ID. Found: ApiGateway, ApiGatewayTwo"

        with self.assertRaisesRegex(GatewayLookupError, error):
            app = FastAPI()
            sam = SAM(self.templates[3])
            sam.configure_api(app)
