from importlib import import_module
import io
import unittest
from pathlib import Path

import yaml

import cloudformation as cf


class TestCloudFormation(unittest.TestCase):
    def test_multi_constructor(self):
        loader = cf.CFLoader(io.StringIO(""))

        tag1 = "GetAtt"
        node1 = yaml.ScalarNode(tag1, "Resource.Arn")
        expected1 = {"Fn::GetAtt": ["Resource", "Arn"]}
        result1 = cf.multi_constructor(loader, tag1, node1)
        self.assertEqual(result1, expected1)

        tag2 = "FindInMap"
        elem1 = yaml.ScalarNode("tag:yaml.org,2002:str", "RegionMap")
        elem2 = yaml.ScalarNode("tag:yaml.org,2002:str", "us-east-1")
        elem3 = yaml.ScalarNode("tag:yaml.org,2002:str", "HVM64")
        node2 = yaml.SequenceNode(tag2, [elem1, elem2, elem3])
        expected2 = {"Fn::FindInMap": ["RegionMap", "us-east-1", "HVM64"]}
        result2 = cf.multi_constructor(loader, tag2, node2)
        self.assertEqual(result2, expected2)

        tag3 = "ToJsonString"
        key = yaml.ScalarNode("tag:yaml.org,2002:str", "Name")
        value = yaml.ScalarNode("tag:yaml.org,2002:str", "Foo")
        node3 = yaml.MappingNode(tag3, ((key, value),))
        expected3 = {"Fn::ToJsonString": {"Name": "Foo"}}
        result3 = cf.multi_constructor(loader, tag3, node3)
        self.assertEqual(result3, expected3)

    def test_multi_constructor_raises_exception(self):
        loader = cf.CFLoader(io.StringIO(""))
        tag_suffix = "Ref"
        node = yaml.nodes.Node("Ref", None, None, None)
        regex = f"!{tag_suffix} <{type(node)}>"

        with self.assertRaisesRegex(cf.CFBadTag, regex):
            cf.multi_constructor(loader, tag_suffix, node)

    def test_construct_getatt(self):
        tag = "Fn::GetAtt"
        expected = ["Resource", "Arn"]

        node1 = yaml.ScalarNode(tag, "Resource.Arn")
        result1 = cf.construct_getatt(node1)
        self.assertEqual(result1, expected)

        elem1 = yaml.ScalarNode("tag:yaml.org,2002:str", "Resource")
        elem2 = yaml.ScalarNode("tag:yaml.org,2002:str", "Arn")
        node2 = yaml.SequenceNode(tag, [elem1, elem2])
        result2 = cf.construct_getatt(node2)
        self.assertEqual(result2, expected)

    def test_construct_getatt_raises_exception(self):
        node = yaml.MappingNode("Ref", {"name": "test"})
        regex = f"^Type <{type(node.value)}>"

        with self.assertRaisesRegex(cf.CFBadNode, regex):
            cf.construct_getatt(node)

    def test_load(self):
        templates = (f"tests/fixtures/templates/example{i}.yml" for i in range(1, 3))

        for template in templates:
            with self.subTest(template=template):
                content = cf.load(template)
                self.assertIsInstance(content, dict)
        else:
            with self.subTest(template=None):
                symlink = Path("template.yml")
                symlink.symlink_to("tests/fixtures/templates/example1.yml")
                content = cf.load()
                symlink.unlink()
                self.assertIsInstance(content, dict)

    def test_load_raises_exception(self):
        template = "unknown.yml"
        regex = f"^{template}$"

        with self.assertRaisesRegex(cf.CFTemplateNotFound, regex):
            cf.load(template)

    def test_list_functions(self):
        template = cf.load("tests/fixtures/templates/example1.yml")

        expected_function = {
            "HelloWorldFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "tests/",
                    "Handler": "fixtures.handlers.app.lambda_handler",
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

        self.assertDictEqual(cf.list_functions(template), expected_function)

    def test_padronize_name(self):
        self.assertEqual(cf.padronize_name("camelCaseExemple"), "camel_case_exemple")

    def test_get_handler(self):
        properties = {
            "CodeUri": "tests/",
            "Handler": "fixtures.handlers.app.lambda_handler",
        }

        handler = cf.get_handler(properties)

        expected_handler = getattr(import_module("tests.fixtures.handlers.app"), "lambda_handler")

        self.assertEqual(handler, expected_handler)

    def test_get_routes(self):
        routes = cf.build_routes(cf.load("tests/fixtures/templates/example1.yml"))

        expected_handler = getattr(import_module("tests.fixtures.handlers.app"), "lambda_handler")

        expected_routes = {
            "DefaultApiGateway": {
                "/hello": {
                    "GET": {
                        "name": "hello_world_function",
                        "handler": expected_handler,
                    },
                }
            }
        }

        self.assertDictEqual(dict(routes), expected_routes)
