import unittest

from fastapi import FastAPI

from adapter import SAM


class TestSAMAdapter(unittest.TestCase):
    def test_initialization(self):
        sam = SAM(FastAPI())
        self.assertIsInstance(sam, SAM)
