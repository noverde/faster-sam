import unittest

from fastapi import routing
from routing import APIRoute


class TestAPIRoute(unittest.TestCase):
    def test_sam_instance_of_api_route(self):
        api_route = APIRoute(path="/api", endpoint=lambda x: ...)
        self.assertIsInstance(api_route, routing.APIRoute)
