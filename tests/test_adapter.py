import unittest

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from adapter import SAM, GatewayLookupError, CustomOpenAPI
from cloudformation import CloudformationTemplate


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

    def test_configure_api_raises_gateway_lookup_error(self):
        error = "^Missing required gateway ID. Found: ApiGateway, ApiGatewayTwo"

        with self.assertRaisesRegex(GatewayLookupError, error):
            app = FastAPI()
            sam = SAM(self.templates[3])
            sam.configure_api(app)

    def test_lambda_handler(self):
        functions = [
            {
                "Properties": {
                    "CodeUri": "hello_world",
                    "Handler": "app.lambda_handler",
                }
            },
            {
                "Properties": {
                    "CodeUri": "hello_world/",
                    "Handler": "app.lambda_handler",
                }
            },
        ]

        sam = SAM(self.templates[0])

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
        app.openapi = CustomOpenAPI(app, self.openapi_schema)

        openapi_schema = app.openapi()

        self.assertEqual(openapi_schema, self.openapi_schema)

    def test_register_route(self):
        examples = [{"bar": "Bar", "baz": 1}]

        class Foo(BaseModel):
            bar: str
            baz: int

            model_config = {"json_schema_extra": {"examples": examples}}

        app = FastAPI()
        app.openapi = CustomOpenAPI(app, self.openapi_schema)

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
