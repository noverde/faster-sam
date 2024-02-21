import unittest

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

    def test_configure_api(self):
        gateways = (None, None, "ApiGateway", "ApiGatewayTwo", None)

        for template, gateway in zip(self.templates, gateways):
            with self.subTest(template=template, gateway=gateway):
                app = FastAPI()
                sam = SAM(template)

                self.assertEqual(len(app.routes), 4)

                sam.configure_api(app, gateway)

                self.assertEqual(len(app.routes), 5)

    def test_configure_multiple_apis(self):
        app = FastAPI()
        subapp = FastAPI()
        app.mount("/subapp", subapp)

        sam = SAM(self.templates[3])
        sam.configure_api(app, "ApiGateway")
        sam.configure_api(subapp, "ApiGatewayTwo")

        self.assertEqual(len(app.routes), 6)
        self.assertEqual(len(subapp.routes), 5)

    def test_configure_queues(self):
        app = FastAPI()
        sam = SAM("tests/fixtures/templates/example6.yml")

        self.assertEqual(len(app.routes), 4)

        sam.configure_queues(app)
        self.assertEqual(len(app.routes), 5)

    def test_configure_api_raises_gateway_lookup_error(self):
        error = "^Missing required gateway ID. Found: ApiGateway, ApiGatewayTwo"

        with self.assertRaisesRegex(GatewayLookupError, error):
            app = FastAPI()
            sam = SAM(self.templates[3])
            sam.configure_api(app)
