import copy
import unittest

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from faster_sam.openapi import custom_openapi


class TestCustomOpenAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("tests/fixtures/templates/swagger.yml") as fp:
            cls.openapi_schema = yaml.safe_load(fp)

    def test_custom_openapi(self):
        server = {"url": "/test"}
        app = FastAPI(servers=[server])
        app.openapi = custom_openapi(app, self.openapi_schema)

        openapi_schema = app.openapi()

        expected_schema = copy.deepcopy(self.openapi_schema)
        expected_schema["servers"].insert(0, server)

        self.assertEqual(openapi_schema, expected_schema)

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
