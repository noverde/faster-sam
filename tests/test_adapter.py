import unittest

from fastapi import FastAPI

from adapter import SAM


class TestSAMAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.path_templates = "tests/fixtures/templates"

    def test_initialization(self):
        sam = SAM(FastAPI())
        self.assertIsInstance(sam, SAM)
