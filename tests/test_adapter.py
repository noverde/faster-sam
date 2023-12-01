import unittest

from fastapi import FastAPI

from adapter import SAM
from cloudformation import CloudformationTemplate


class TestSAM(unittest.TestCase):
    def test_initialization(self):
        templates = [
            {"template_path": "tests/fixtures/templates/example1.yml", "expected_route_count": 1},
            {"template_path": "tests/fixtures/templates/example2.yml", "expected_route_count": 2},
            {"template_path": "tests/fixtures/templates/example3.yml", "expected_route_count": 2},
        ]

        for template in templates:
            with self.subTest(template_path=template["template_path"]):
                app = FastAPI()
                sam = SAM(app, template["template_path"])

                self.assertIsInstance(sam, SAM)
                self.assertEqual(id(app), id(sam.app))
                self.assertIsInstance(sam.template, CloudformationTemplate)
                self.assertIsInstance(sam.routes, dict)
                self.assertGreaterEqual(len(sam.routes), template["expected_route_count"])

    def test_lambda_handler(self):
        app = FastAPI()
        sam = SAM(app, "tests/fixtures/templates/example1.yml")

        resources = [
            {
                "Properties": {
                    "CodeUri": "hello_world",
                    "Handler": "app.lambda_handler",
                },
            },
            {
                "Properties": {
                    "CodeUri": "hello_world/",
                    "Handler": "app.lambda_handler",
                },
            },
        ]

        for resource in resources:
            with self.subTest():
                handler_path = sam.lambda_handler(resource["Properties"])

                self.assertEqual(handler_path, "hello_world.app.lambda_handler")
