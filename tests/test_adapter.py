import unittest
from importlib import import_module

from fastapi import FastAPI

from adapter import SAM


class TestSAMAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.path_templates = "tests/fixtures/templates"

    def test_sam_instance_of_fastapi(self):
        sam = SAM(f"{self.path_templates}/example1.yml")
        self.assertIsInstance(sam, FastAPI)

    def test_get_routes(self):
        sam = SAM(f"{self.path_templates}/example1.yml")
        expected_handler = getattr(import_module("tests.fixtures.handlers.app"), "lambda_handler")
        expected_routes = {
            "DefaultApiGateway": {
                "/hello": {
                    "GET": {
                        "name": "hello_world_function",
                        "handler": expected_handler,
                    },
                }
            }
        }
        self.assertDictEqual(dict(sam.routes), expected_routes)
