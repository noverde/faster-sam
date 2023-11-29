import unittest
from pathlib import Path

from adapter import SAM
from cloudformation import CFTemplateNotFound


class TestSAMAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.path_templates = "tests/fixtures/templates"

    def test_initialization_with_template(self):
        sam = SAM(f"{self.path_templates}/example1.yml")
        self.assertIsInstance(sam, SAM)

    def test_initialization_without_template(self):
        symlink = Path("template.yml")
        symlink.symlink_to("tests/fixtures/templates/example1.yml")

        sam = SAM()
        symlink.unlink()

        self.assertIsInstance(sam, SAM)

    def test_initialization_without_template_exception(self):
        with self.assertRaises(CFTemplateNotFound):
            SAM()
