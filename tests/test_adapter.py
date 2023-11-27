import unittest

from fastapi import routing, FastAPI

from adapter import SAM, APIRoute


class TestSAMAdapter(unittest.TestCase):
    def test_sam_instance_of_fastapi(self):
        sam = SAM()
        self.assertIsInstance(sam, FastAPI)


class TestAPIRoute(unittest.TestCase):
    def test_sam_instance_of_api_route(self):
        api_route = APIRoute(path="/api", endpoint=lambda x: ...)
        self.assertIsInstance(api_route, routing.APIRoute)
