import json
import unittest

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from faster_sam.middlewares import bucket_path_rewriter


class TestBucketPathRewriterMiddleware(unittest.TestCase):

    def setUp(self) -> None:
        async def bucket(request: Request) -> Response:
            return Response(content=json.dumps({"path": request.scope["path"]}))

        app = FastAPI()
        app.add_middleware(bucket_path_rewriter.BucketPathRewriterMiddleware)
        app.add_route("/bucket", bucket)

        self.client = TestClient(app)

    async def test_middleware_rewrite_path_with_bucket(self):
        response = self.client.post("/bucket", json={"bucket": "test-bucket-123"})

        self.assertEqual(json.loads(response.body), {"path": "/test-bucket-123"})

    async def test_middleware_rewrite_path_with_empty_body(self):
        response = self.client.post("/bucket", json={})

        self.assertEqual(json.loads(response.body), {"message": "Invalid Request"})

    async def test_middleware_rewrite_path_without_post(self):
        response = self.client.get("/bucket")

        self.assertEqual(json.loads(response.body), {"path": "/"})
