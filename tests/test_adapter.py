import unittest

from fastapi import FastAPI

from adapter import SAM
from cloudformation import CFTemplateNotFound


class TestSAMAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.path_templates = "tests/fixtures/templates"

    def test_sam_instance_of_fastapi(self):
        sam = SAM(f"{self.path_templates}/example1.yml")
        self.assertIsInstance(sam, FastAPI)

    def test_initialization_with_template(self):
        sam = SAM(f"{self.path_templates}/example1.yml")

        self.assertIsNotNone(sam._cloudformation)
        self.assertIsInstance(sam._cloudformation, dict)
        self.assertIn("Resources", sam._cloudformation)

    def test_initialization_without_template_exception(self):
        with self.assertRaises(CFTemplateNotFound):
            SAM()
