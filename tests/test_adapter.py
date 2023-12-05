import unittest

from fastapi import FastAPI

from adapter import SAM
from cloudformation import CloudformationTemplate
from routing import APIRoute


class TestSAM(unittest.TestCase):
    def test_initialization(self):
        scenarios = [
            {
                "template_path": "tests/fixtures/templates/example1.yml",
                "gateway_count": 1,
                "gateway_name": "ImplicitGateway",
            },
            {
                "template_path": "tests/fixtures/templates/example2.yml",
                "gateway_count": 2,
                "gateway_name": "ApiGateway",
            },
            {
                "template_path": "tests/fixtures/templates/example3.yml",
                "gateway_count": 2,
                "gateway_name": "ApiGateway",
            },
        ]

        for scenario in scenarios:
            with self.subTest(**scenario):
                app = FastAPI()
                sam = SAM(app, scenario["template_path"])
                key = scenario["gateway_name"]
                routes_count = sum(1 for r in app.routes if isinstance(r, APIRoute))

                self.assertIsInstance(sam, SAM)
                self.assertEqual(id(app), id(sam.app))
                self.assertIsInstance(sam.template, CloudformationTemplate)
                self.assertIsInstance(sam.routes, dict)
                self.assertGreaterEqual(len(sam.routes), scenario["gateway_count"])
                self.assertGreaterEqual(len(sam.routes[key]), 1)
                self.assertEqual(routes_count, 1)

    def test_lambda_handler(self):
        app = FastAPI()
        sam = SAM(app, "tests/fixtures/templates/example1.yml")

        functions = [
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

        for function in functions:
            with self.subTest():
                handler_path = sam.lambda_handler(function["Properties"])

                self.assertEqual(handler_path, "hello_world.app.lambda_handler")
