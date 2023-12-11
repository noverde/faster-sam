import unittest

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from adapter import SAM, custom_openapi
from cloudformation import CloudformationTemplate


class TestSAM(unittest.TestCase):
    def test_initialization(self):
        templates = (
            "tests/fixtures/templates/example1.yml",
            "tests/fixtures/templates/example2.yml",
            "tests/fixtures/templates/example3.yml",
        )

        for template in templates:
            with self.subTest(template=template):
                sam = SAM(template)

                self.assertIsInstance(sam, SAM)
                self.assertIsInstance(sam.template, CloudformationTemplate)

    def test_lambda_handler(self):
        sam = SAM("tests/fixtures/templates/example1.yml")

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
            with self.subTest(**function["Properties"]):
                handler_path = sam.lambda_handler(function["Properties"])
                self.assertEqual(handler_path, "hello_world.app.lambda_handler")


class TestCustomOpenAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("tests/fixtures/templates/swagger.yml") as fp:
            cls.openapi_schema = yaml.safe_load(fp)

    def test_custom_openapi(self):
        app = FastAPI()
        app.openapi = custom_openapi(app, self.openapi_schema)

        openapi_schema = app.openapi()

        self.assertEqual(openapi_schema, self.openapi_schema)

    def test_register_route(self):
        examples = [{"bar": "Bar", "baz": 1}]

        class Foo(BaseModel):
            bar: str
            baz: int

            model_config = {"json_schema_extra": {"examples": examples}}

        app = FastAPI()
        app.openapi = custom_openapi(app, self.openapi_schema)

        @app.post("/foo")
        def _(foo: Foo):
            return foo

        self.assertIsNone(app.openapi_schema)

        schema1 = app.openapi()

        self.assertIsNotNone(app.openapi_schema)
        self.assertIn("/foo", schema1["paths"])
        self.assertEqual(schema1["components"]["schemas"]["Foo"]["examples"], examples)

        schema2 = app.openapi()
        self.assertIs(schema1, schema2)
