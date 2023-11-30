import io
import unittest
from pathlib import Path

import yaml

import cloudformation as cf
from cloudformation import Template


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


class TestTemplate(unittest.TestCase):
    def setUp(self):
        self.function = {
            "HelloWorldFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "hello_world/",
                    "Handler": "app.lambda_handler",
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

    def test_load(self):
        templates = (f"tests/fixtures/templates/example{i}.yml" for i in range(1, 3))

        for template in templates:
            with self.subTest(template=template):
                cloudformation = Template(template)
                self.assertIsInstance(cloudformation.template, dict)
        else:
            with self.subTest(template=None):
                symlink = Path("template.yml")
                symlink.symlink_to("tests/fixtures/templates/example1.yml")
                cloudformation = Template()
                symlink.unlink()
                self.assertIsInstance(cloudformation.template, dict)

    def test_load_raises_exception(self):
        template = "unknown.yml"
        regex = f"^{template}$"

        with self.assertRaisesRegex(cf.CFTemplateNotFound, regex):
            Template(template)

    def test_list_functions(self):
        cloudformation = Template("tests/fixtures/templates/example1.yml")

        expected_functions = [self.function]

        self.assertEqual(cloudformation.functions, expected_functions)

    def test_list_gateways(self):
        cloudformation = Template("tests/fixtures/templates/example2.yml")

        expected_gateways = [
            {
                "ApiGateway": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "Name": "sam-api",
                        "StageName": "v1",
                    },
                },
            },
        ]

        self.assertEqual(cloudformation.gateways, expected_gateways)

    def test_find_nodes(self):
        cloudformation = Template("tests/fixtures/templates/example1.yml")
        tree = cloudformation.template
        nodes = cloudformation.find_nodes(tree["Resources"], cf.NodeType.LAMBDA)

        expected_nodes = [self.function]

        self.assertEqual(nodes, expected_nodes)
