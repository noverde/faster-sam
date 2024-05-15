import json
import unittest

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from faster_sam.middlewares import queue_path_rewriter


class TestQueuePathRewriterMiddleware(unittest.TestCase):
    def setUp(self) -> None:
        async def queue(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        app = FastAPI()
        app.add_middleware(queue_path_rewriter.QueuePathRewriterMiddleware)
        app.add_route("/queue", queue)

        self.client = TestClient(app)

    async def test_middleware_rewrite_path(self):
        response = self.client.post(
            "/queue", json={"message": {"attributes": {"endpoint": "/foo/bar"}}}
        )

        self.assertEqual(json.loads(response.body), {"path": "/bar"})

    async def test_middleware_rewrite_path_with_empty_body(self):
        response = self.client.post("/queue", json={})

        self.assertEqual(json.loads(response.body), {"message": "Invalid Request"})

    async def test_middleware_rewrite_path_without_post(self):
        response = self.client.get("/queue")

        self.assertEqual(json.loads(response.body), {"path": "/foo"})
