import unittest
from fastapi import FastAPI
from src.adapter import SAM


class TestSAMAdapter(unittest.TestCase):
    def test_sam_instance_of_fastapi(self):
        sam = SAM()
        self.assertIsInstance(sam, FastAPI)
