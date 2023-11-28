import unittest
from pathlib import Path

from adapter import SAM
from cloudformation import CFTemplateNotFound


class TestSAMAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.path_templates = "tests/fixtures/templates"

    def test_initialization_with_template(self):
        sam = SAM(f"{self.path_templates}/example1.yml")

        self.assertIsNotNone(sam._cloudformation)
        self.assertIsInstance(sam._cloudformation, dict)
        self.assertIn("Resources", sam._cloudformation)

    def test_initialization_without_template(self):
        symlink = Path("template.yml")
        symlink.symlink_to("tests/fixtures/templates/example1.yml")

        sam = SAM()

        symlink.unlink()

        self.assertIsNotNone(sam._cloudformation)
        self.assertIsInstance(sam._cloudformation, dict)
        self.assertIn("Resources", sam._cloudformation)

    def test_initialization_without_template_exception(self):
        with self.assertRaises(CFTemplateNotFound):
            SAM()

    def load_routes_from_cloudformation(self):
        sam = SAM(f"{self.path_templates}/example1.yml")
        routes = sam.load_routes_from_cloudformation()

        expected_routes = {
            "DefaultApiGateway": {
                "/hello": {
                    "GET": {
                        "name": "hello_world_function",
                        "handler": "app.lambda_handler",
                    },
                }
            }
        }

        self.assertDictEqual(dict(routes), expected_routes)
