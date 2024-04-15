import io
import json
import sys
import unittest
from unittest.mock import patch

from faster_sam.cmd import faster


class TestCmdFaster(unittest.TestCase):
    def test_faster(self):
        expected = {
            "HelloWorldFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "tests/",
                    "Handler": "fixtures.handlers.lambda_handler.handler",
                    "Runtime": "python3.11",
                    "Architectures": ["x86_64"],
                    "Events": {
                        "HelloWorld": {
                            "Type": "Api",
                            "Properties": {"Path": "/hello", "Method": "get"},
                        }
                    },
                },
            }
        }

        args = [
            "faster",
            "resources",
            "list",
            "-f",
            "tests/fixtures/templates/example1.yml",
            "-t",
            "functions",
            "-o",
            "json",
        ]

        with patch.object(sys, "argv", args):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                faster.main()

                self.assertEqual(json.loads(mock_stdout.getvalue()), expected)
