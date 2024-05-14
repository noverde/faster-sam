import json
import unittest

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

from faster_sam.middlewares.remove_path import RemovePathMiddleware


class TestRemovePathMiddleware(unittest.TestCase):
    def setUp(self) -> None:
        async def homepage(request: Request) -> Response:
            return Response(content=json.dumps({"message": "Hello, World"}))

        app = FastAPI()
        app.add_middleware(RemovePathMiddleware, path="/foo")
        app.add_route("/bar", homepage)

        self.client = TestClient(app)

    def test_remove_path(self) -> None:
        response = self.client.get("/foo/bar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Hello, World"})
