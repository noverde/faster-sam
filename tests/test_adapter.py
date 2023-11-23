import os
import unittest

from fastapi import FastAPI

from adapter import SAM


class TestSAMAdapter(unittest.TestCase):
    def test_sam_instance_of_fastapi(self):
        sam = SAM()
        self.assertIsInstance(sam, FastAPI)

    def test_read_yml_file(self):
        sam = SAM()

        current_path = os.path.dirname(os.path.abspath(__file__))

        file_path = os.path.join(current_path, "template.yaml")

        file = sam.read_yml_file(file_path)

        self.assertIsNotNone(file)
        self.assertIsInstance(file, dict)
        self.assertIn("Resources", file)
