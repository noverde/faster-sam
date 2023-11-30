import unittest

from fastapi import FastAPI

from adapter import SAM
from cloudformation import CloudformationTemplate


class TestSAM(unittest.TestCase):
    def test_initialization(self):
        app = FastAPI()
        template_path = "tests/fixtures/templates/example2.yml"
        sam = SAM(app, template_path)

        self.assertIsInstance(sam, SAM)
        self.assertEqual(id(app), id(sam.app))
        self.assertIsInstance(sam.template, CloudformationTemplate)
        self.assertIsInstance(sam.routes, dict)
        self.assertGreater(len(sam.routes), 0)
