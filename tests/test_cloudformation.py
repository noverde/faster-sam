import io
import unittest
from contextlib import contextmanager
from pathlib import Path

import yaml

import faster_sam.cloudformation as cf
from faster_sam.cloudformation import CloudformationTemplate, IntrinsicFunctions


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

        self.gateways = {
            "ApiGateway": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                    "Name": "sam-api",
                    "StageName": "v1",
                },
            },
        }

        self.queues = {
            "DatabasesQueue": {
                "Type": "AWS::SQS::Queue",
                "Properties": {
                    "QueueName": "my-queue",
                    "VisibilityTimeout": 120,
                    "RedrivePolicy": {
                        "deadLetterTargetArn": {
                            "Fn::GetAtt": "DatabasesDLQ.Arn",
                        },
                        "maxReceiveCount": 3,
                    },
                },
            },
            "DatabasesDLQ": {
                "Type": "AWS::SQS::Queue",
                "Properties": {
                    "VisibilityTimeout": 120,
                    "MessageRetentionPeriod": 1209600,
                    "QueueName": "my-queue-dlq",
                },
            },
        }

        self.template_1 = "tests/fixtures/templates/example1.yml"

    def test_load(self):
        templates = (f"tests/fixtures/templates/example{i}.yml" for i in range(1, 3))

        with open("tests/fixtures/templates/swagger.yml") as fp:
            swagger = yaml.safe_load(fp)

        for template, definition_body in zip(templates, (None, None, swagger)):
            with self.subTest(template=template, definition_body=definition_body):
                cloudformation = CloudformationTemplate(template)
                self.assertIsInstance(cloudformation.template, dict)
                api_gateway = cloudformation.template["Resources"].get(
                    "ApiGateway", {"Properties": {}}
                )
                self.assertEqual(api_gateway["Properties"].get("DefinitionBody"), definition_body)
        else:
            with self.subTest(template=None):
                with link("template.yml", self.template_1):
                    cloudformation = CloudformationTemplate()

                self.assertIsInstance(cloudformation.template, dict)

    def test_load_with_params(self):
        cloudformation = CloudformationTemplate(
            "tests/fixtures/templates/example2.yml", {"Environment": "development"}
        )

        self.assertEqual(
            cloudformation.template["Parameters"]["Environment"]["Default"],
            "development",
        )

    def test_load_raises_exception(self):
        template = "unknown.yml"
        regex = f"^{template}$"

        with self.assertRaisesRegex(cf.CFTemplateNotFound, regex):
            CloudformationTemplate(template)

    def test_list_functions(self):
        cloudformation = CloudformationTemplate(self.template_1)

        for function in cloudformation.functions.values():
            with self.subTest(function=function.resource):
                self.assertEqual(function.resource, self.functions[function.id])

    def test_list_gateways(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example2.yml")

        for api in cloudformation.apis.values():
            with self.subTest(api=api.resource):
                self.assertEqual(api.resource, self.gateways[api.id])

    def test_list_queues(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example6.yml")

        for queue in cloudformation.queues.values():
            with self.subTest(queue=queue.resource):
                self.assertEqual(queue.resource, self.queues[queue.id])

    def test_list_buckets(self):
        buckets = {
            "TestBucket": {
                "Type": "AWS::S3::Bucket",
                "DeletionPolicy": "Retain",
                "Properties": {"BucketName": "test-bucket"},
            }
        }

        cloudformation = CloudformationTemplate("tests/fixtures/templates/example7.yml")

        for bucket in cloudformation.buckets.values():
            with self.subTest(bucket=bucket.resource):
                self.assertEqual(bucket.resource, buckets[bucket.id])

    def test_list_environment(self):
        scenarios = {
            "tests/fixtures/templates/example1.yml": {},
            "tests/fixtures/templates/example2.yml": {
                "ENVIRONMENT": "development",
                "LOG_LEVEL": "DEBUG",
                "SENDER_ACCOUNT": "tests/",
                "HANDLER": "fixtures.handlers.lambda_handler.handler",
            },
            "tests/fixtures/templates/example3.yml": {
                "ENVIRONMENT": "development",
                "LOG_LEVEL": "DEBUG",
                "STAGE_NAME": "v1",
            },
            "tests/fixtures/templates/example4.yml": {
                "ENVIRONMENT": "development",
                "LOG_LEVEL": "DEBUG",
            },
        }

        for template, expected in scenarios.items():
            with self.subTest(template=template, expected=expected):
                cloudformation = CloudformationTemplate(
                    template, parameters={"Environment": "development"}
                )
                self.assertEqual(cloudformation.environment, expected)

    def test_find_nodes(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example1.yml")
        tree = cloudformation.template
        nodes = cloudformation.find_nodes(tree["Resources"], cf.ResourceType.FUNCTION)

        self.assertEqual(nodes, self.functions)

    def test_lambda_handler(self):
        cloudformation = CloudformationTemplate("tests/fixtures/templates/example5.yml")
        functions = {
            "HelloWorldFunction": {
                "Properties": {
                    "CodeUri": "tests/",
                    "Handler": "fixtures.handlers.lambda_handler.handler",
                }
            },
            "HelloNameFunction": {
                "Properties": {
                    "CodeUri": "tests/",
                    "Handler": "fixtures.handlers.lambda_handler.handler",
                }
            },
            "NoTriggersFunction": {
                "Properties": {
                    "CodeUri": "tests/",
                    "Handler": "fixtures.handlers.lambda_handler.handler",
                }
            },
        }
        for key, function in functions.items():
            with self.subTest(**function["Properties"]):
                handler_path = cloudformation.functions[key].handler
                self.assertEqual(handler_path, "tests.fixtures.handlers.lambda_handler.handler")


class TestIntrinsicFunctions(unittest.TestCase):
    def test_getatt_function(self):
        scenarios = {
            "Resolved Function": {
                "template": "tests/fixtures/templates/example3.yml",
                "function": {"Fn::GetAtt": ["ApiGateway", {"Ref": "AttributeName"}]},
                "expected": "v1",
            },
            "Attribute ID is None": {
                "template": "tests/fixtures/templates/example3.yml",
                "function": {"Fn::GetAtt": ["ApiFunction", {"Ref": "AttributeName"}]},
                "expected": None,
            },
            "Attribute Name is None": {
                "template": "tests/fixtures/templates/example3.yml",
                "function": {"Fn::GetAtt": ["ApiGateway", "attibute"]},
                "expected": None,
            },
            "Unresolved Attribute Function": {
                "template": "tests/fixtures/templates/example3.yml",
                "function": {"Fn::GetAtt": ["ApiGateway", {"Ref": "Attribute"}]},
                "expected": None,
            },
            "Unresolved Function Return Value": {
                "template": "tests/fixtures/templates/example3.yml",
                "function": {"Fn::GetAtt": ["ApiGateway", "Tags"]},
                "expected": None,
            },
        }

        for key, values in scenarios.items():
            with self.subTest(case=key, template=values["template"]):
                cloudformation = CloudformationTemplate(
                    values["template"], parameters={"Environment": "development"}
                )
                value = IntrinsicFunctions.eval(values["function"], cloudformation.template)

                self.assertEqual(value, values["expected"])

    def test_join_function(self):
        scenarios = {
            "Resolved Function": {
                "template": "tests/fixtures/templates/example2.yml",
                "function": {
                    "Fn::Join": [
                        ".",
                        ["fixtures", "handlers", "lambda_handler", {"Ref": "Handler"}],
                    ]
                },
                "expected": "fixtures.handlers.lambda_handler.handler",
            },
            "Unresolved Function with Incorrect Reference": {
                "template": "tests/fixtures/templates/example2.yml",
                "function": {
                    "Fn::Join": [
                        ".",
                        ["fixtures", "handlers", "lambda_handler", {"Ref": "fixture"}],
                    ]
                },
                "expected": None,
            },
        }

        for key, values in scenarios.items():
            with self.subTest(case=key, template=values["template"]):
                cloudformation = CloudformationTemplate(
                    values["template"], parameters={"Environment": "development"}
                )
                value = IntrinsicFunctions.eval(values["function"], cloudformation.template)

                self.assertEqual(value, values["expected"])


class TestResource(unittest.TestCase):
    def test_resource(self):
        resource_id = "Test"
        resource = {
            "Type": "AWS::Serverless::Function",
            "Properties": {"FunctionName": "test"},
        }

        instance = cf.Resource(resource_id, resource)

        self.assertEqual(instance.id, resource_id)
        self.assertEqual(instance.resource, resource)


class TestEventSource(unittest.TestCase):
    def test_event_source(self):
        resource_id = "TestApi"
        resource = {
            "Type": "Api",
            "Properties": {"Path": "/test", "Method": "get"},
        }

        instance = cf.EventSource.from_resource(resource_id, resource)

        self.assertEqual(instance.type, cf.EventType.API)


class TestFunction(unittest.TestCase):
    def setUp(self):
        self.event_id = "TestApi"
        self.event = {
            "Type": "Api",
            "Properties": {"Path": "/test", "Method": "get"},
        }

        self.resource_id = "TestFunction"
        self.resource = {
            "Type": "AWS::Serverless::Function",
            "Properties": {
                "FunctionName": "test",
                "CodeUri": "src/",
                "Handler": "lambda_handler.handler",
                "Environment": {"Variables": {"ENVIRONMENT": "development"}},
                "Events": {
                    self.event_id: self.event,
                    "TestSQS": {
                        "Type": "SQS",
                        "Properties": {"Queue": "arn:aws:sqs:us-west-2:012345678901:test-queue"},
                    },
                },
            },
        }

    def test_function(self):
        instance = cf.Function(self.resource_id, self.resource)

        self.assertEqual(instance.name, "test")
        self.assertEqual(instance.handler, "src.lambda_handler.handler")
        self.assertEqual(instance.environment, {"ENVIRONMENT": "development"})
        self.assertEqual(instance.events[self.event_id].type, cf.EventType.API)

    def test_filtered_events(self):
        instance = cf.Function(self.resource_id, self.resource)

        for event in instance.filtered_events(cf.EventType.API).values():
            with self.subTest(event=event):
                self.assertEqual(event.type, cf.EventType.API)


class TestApi(unittest.TestCase):
    def test_api(self):
        resource_id = "ApiGateway"
        resource = {
            "Type": "AWS::Serverless::Api",
            "Properties": {
                "Name": "api",
                "StageName": "v1",
                "DefinitionBody": {
                    "Fn::Transform": {
                        "Name": "AWS::Include",
                        "Parameters": {
                            "Location": "./swagger.yml",
                        },
                    },
                },
            },
        }

        instance = cf.Api(resource_id, resource)

        self.assertEqual(instance.name, "api")
        self.assertEqual(instance.stage_name, "v1")


class TestApiEvent(unittest.TestCase):
    def test_api_event(self):
        resource_id = "TestApi"
        resource = {
            "Type": "Api",
            "Properties": {
                "RestApiId": {"Ref": "ApiGateway"},
                "Path": "/test",
                "Method": "get",
            },
        }

        instance = cf.ApiEvent(resource_id, resource)

        self.assertEqual(instance.rest_api_id, "ApiGateway")
        self.assertEqual(instance.path, "/test")
        self.assertEqual(instance.method, "get")
        self.assertEqual(instance.type, cf.EventType.API)


class TestQueue(unittest.TestCase):
    def test_queue(self):
        resource_id = "TestQueue"
        resource = {
            "Type": "AWS::SQS::Queue",
            "Properties": {
                "QueueName": "test-queue",
                "VisibilityTimeout": 120,
                "MessageRetentionPeriod": 1209600,
                "RedrivePolicy": {
                    "deadLetterTargetArn": "arn:aws:sqs:us-west-2:012345678901:test-queue",
                    "maxReceiveCount": 3,
                },
            },
        }

        instance = cf.Queue(resource_id, resource)

        self.assertEqual(instance.name, "test-queue")
        self.assertEqual(instance.visibility_timeout, 120)
        self.assertEqual(instance.message_retention_period, 1209600)
        self.assertEqual(
            instance.redrive_policy,
            {
                "deadLetterTargetArn": "arn:aws:sqs:us-west-2:012345678901:test-queue",
                "maxReceiveCount": 3,
            },
        )


class TestBucket(unittest.TestCase):
    def test_bucket(self):
        resource_id = "TestBucket"
        resource = {
            "Type": "AWS::S3::Bucket",
            "DeletionPolicy": "Retain",
            "Properties": {
                "BucketName": "test-bucket",
            },
        }

        instance = cf.Bucket(resource_id, resource)

        self.assertEqual(instance.name, "test-bucket")


class TestSQSEvent(unittest.TestCase):
    def test_sqs_event(self):
        resource_id = "TestSQS"
        resource = {
            "Type": "SQS",
            "Properties": {
                "Queue": "arn:aws:sqs:us-west-2::test-queue",
                "BatchSize": 10,
            },
        }

        instance = cf.SQSEvent(resource_id, resource)

        self.assertEqual(instance.queue, "arn:aws:sqs:us-west-2::test-queue")
        self.assertEqual(instance.batch_size, 10)
        self.assertEqual(instance.type, cf.EventType.SQS)


class TestScheduleEvent(unittest.TestCase):
    def test_schedule_event(self):
        resource_id = "TestSchedule"
        resource = {
            "Type": "Schedule",
            "Properties": {
                "Schedule": "rate(1 minute)",
            },
        }

        instance = cf.ScheduleEvent(resource_id, resource)

        self.assertEqual(instance.schedule, "rate(1 minute)")
        self.assertEqual(instance.type, cf.EventType.SCHEDULE)
