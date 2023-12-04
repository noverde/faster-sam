import io
import unittest
from contextlib import contextmanager
from pathlib import Path

import yaml

import cloudformation as cf
from cloudformation import CloudformationTemplate


@contextmanager
def link(link, target):
    symlink = Path(link)
    try:
        yield symlink.symlink_to(target)
    finally:
        symlink.unlink()


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


class TestCloudformationTemplate(unittest.TestCase):
    def setUp(self):
        self.functions = {
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

        self.gateways = {
            "ApiGateway": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                    "Name": "sam-api",
                    "StageName": "v1",
                },
            },
        }

        self.template_1 = "tests/fixtures/templates/example1.yml"

    def test_load(self):
        templates = (f"tests/fixtures/templates/example{i}.yml" for i in range(1, 3))

        for template in templates:
            with self.subTest(template=template):
                cloudformation = CloudformationTemplate(template)
                self.assertIsInstance(cloudformation.template, dict)
        else:
            with self.subTest(template=None):
                with link("template.yml", self.template_1):
                    cloudformation = CloudformationTemplate()

                self.assertIsInstance(cloudformation.template, dict)

    def test_load_raises_exception(self):
        template = "unknown.yml"
        regex = f"^{template}$"

        with self.assertRaisesRegex(cf.CFTemplateNotFound, regex):
            CloudformationTemplate(template)

    def test_list_functions(self):
        cloudformation = CloudformationTemplate(self.template_1)

        self.assertEqual(cloudformation.functions, self.functions)

    def test_list_gateways(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example2.yml")

        self.assertEqual(cloudformation.gateways, self.gateways)

    def test_find_nodes(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example1.yml")
        tree = cloudformation.template
        nodes = cloudformation.find_nodes(tree["Resources"], cf.NodeType.LAMBDA)

        self.assertEqual(nodes, self.functions)

    def test_load_with_swagger(self):
        template = "tests/fixtures/templates/example3.yml"

        with link("swagger.yml", "tests/fixtures/templates/swagger.yml"):
            cloudformation = CloudformationTemplate(template)

        self.assertIsInstance(cloudformation.template, dict)

        swagger = {
            "openapi": "3.0.1",
            "info": {
                "title": "SAM API",
                "description": "Sample SAM API",
                "version": "v1.0",
                "contact": {"email": "developers@mail.com"},
            },
            "servers": [{"url": "https://hello.mydomain.com", "description": "Sample SAM API"}],
            "x-amazon-apigateway-request-validator": "all",
            "x-amazon-apigateway-request-validators": {
                "all": {"validateRequestBody": True, "validateRequestParameters": True}
            },
            "x-amazon-apigateway-cors": {
                "allowOrigins": ["*"],
                "allowMethods": ["OPTIONS", "GET"],
                "allowHeaders": ["Content-Type"],
            },
            "components": {
                "schemas": {
                    "HelloResponse": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                    }
                },
                "examples": {
                    "HelloResponse": {
                        "summary": "An example of hello message",
                        "value": {"message": "Hello World!"},
                    }
                },
            },
            "tags": [{"name": "Hello"}],
            "paths": {
                "/hello/{name}": {
                    "get": {
                        "operationId": "sayHello",
                        "tags": ["Hello"],
                        "summary": "Say hello",
                        "description": "Returns a greeting message",
                        "parameters": [
                            {
                                "in": "path",
                                "name": "name",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "Your name",
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/HelloResponse"},
                                        "examples": {
                                            "address_response": {
                                                "$ref": "#/components/examples/HelloResponse"
                                            }
                                        },
                                    }
                                },
                            },
                            "400": {"description": "Bad Request"},
                            "500": {"description": "Internal Server Error"},
                        },
                        "x-amazon-apigateway-integration": {
                            "passthroughBehavior": "when_no_match",
                            "httpMethod": "POST",
                            "type": "aws_proxy",
                            "uri": {
                                "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/"
                                "2015-03-31/functions/${HelloWorldFunction.Arn}/invocations"
                            },
                            "credentials": {
                                "Fn::Sub": "arn:aws:iam::${AWS::AccountId}:role/"
                                "apigateway-invoke-lambda-role"
                            },
                        },
                    }
                }
            },
        }

        self.assertIsInstance(swagger, dict)
        self.assertDictEqual(
            swagger,
            cloudformation.gateways["ApiGateway"]["Properties"]["DefinitionBody"],
        )
        self.assertEqual(
            id(cloudformation.gateways["ApiGateway"]["Properties"]["DefinitionBody"]),
            id(cloudformation.template["Resources"]["ApiGateway"]["Properties"]["DefinitionBody"]),
        )
