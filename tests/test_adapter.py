import unittest

from fastapi import FastAPI
import yaml

from adapter import SAM, custom_openapi
from cloudformation import CloudformationTemplate
from routing import APIRoute
from pydantic import BaseModel


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


class Foo(BaseModel):
    foo: str
    bar: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "foo": 1,
                    "bar": "Foo",
                }
            ]
        }
    }


class TestCustomOpenAPI(unittest.TestCase):
    def setUp(self) -> None:
        with open("tests/fixtures/templates/swagger.yml") as fp:
            self.openapi_schema = yaml.safe_load(fp)

    def test_custom_load_openapi(self):
        app = FastAPI()

        app.openapi = custom_openapi(app, self.openapi_schema)

        openapi = app.openapi()

        self.assertDictEqual(self.openapi_schema["paths"], openapi["paths"])
        self.assertDictEqual(self.openapi_schema["components"], openapi["components"])

    def test_register_route(self):
        app = FastAPI()

        @app.post("/foo")
        async def handler(body: Foo):
            return {"response": body}

        app.openapi = custom_openapi(app, self.openapi_schema)

        openapi = app.openapi()

        foo_expected_example = Foo.model_config["json_schema_extra"]["examples"][0]
        foo_actual_example = openapi["components"]["schemas"]["Foo"]["examples"][0]

        self.assertIn("/foo", openapi["paths"])
        self.assertDictEqual(foo_expected_example, foo_actual_example)
