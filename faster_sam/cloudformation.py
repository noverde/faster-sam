import base64
import logging
from enum import Enum
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

import yaml

PREFIX = "Fn::"
WITHOUT_PREFIX = ("Ref", "Condition")

logger = logging.getLogger(__name__)


class CFTemplateNotFound(FileNotFoundError):
    """Raised when the CloudFormation template file cannot be found."""

    pass


class CFBadTag(TypeError):
    """Raised when an invalid CloudFormation tag is encountered."""

    pass


class CFBadNode(ValueError):
    """Raised when an invalid CloudFormation node is encountered."""

    pass


class CFLoader(yaml.SafeLoader):
    """Custom YAML loader for CloudFormation templates."""

    pass


class ResourceType(Enum):
    """
    Enum representing different types of AWS resources.

    Attributes
    ----------
    API : str
        Represents the "AWS::Serverless::Api" node type.
    FUNCTION : str
        Represents the "AWS::Serverless::Function" node type.
    QUEUE : str
        Represents the "AWS::SQS::Queue" node type.
    BUCKET : str
        Represents the "AWS::S3::Bucket" node type.
    """

    API = "AWS::Serverless::Api"
    FUNCTION = "AWS::Serverless::Function"
    QUEUE = "AWS::SQS::Queue"
    BUCKET = "AWS::S3::Bucket"


class EventType(Enum):
    """
    Enum representing different types of AWS resource events.

    Attributes
    ----------
    API : str
        Represents the "Api" node type.
    SQS : str
        Represents the "SQS" node type.
    SCHEDULE : str
        Represents the "Schedule" node type.
    """

    API = "Api"
    SQS = "SQS"
    SCHEDULE = "Schedule"


def multi_constructor(loader: CFLoader, tag_suffix: str, node: yaml.nodes.Node) -> Dict[str, Any]:
    """
    Custom YAML node constructor.

    Handles AWS CloudFormation extensions for its short version of intrinsic functions.

    Parameters
    ----------
    loader : CFLoader
        The YAML loader instance.
    tag_suffix : str
        The YAML tag suffix.
    node : yaml.nodes.Node
        The YAML node.

    Returns
    -------
    Dict[str, Any]
        A dictionary representation of the given YAML node.

    Raises
    ------
    CFBadTag
        If an invalid CloudFormation tag is encountered.
    """

    tag = tag_suffix

    if tag not in WITHOUT_PREFIX:
        tag = f"{PREFIX}{tag}"

    if tag == "Fn::GetAtt":
        return {tag: construct_getatt(node)}
    elif isinstance(node, yaml.ScalarNode):
        return {tag: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag: loader.construct_mapping(node)}

    raise CFBadTag(f"!{tag} <{type(node)}>")


def construct_getatt(node: yaml.nodes.Node) -> List[Any]:
    """
    Custom YAML node constructor for AWS CloudFormation GetAtt intrinsic function.

    Parameters
    ----------
    node : yaml.nodes.Node
        The node representing a CloudFormation GetAtt element.

    Returns
    -------
    List[Any]
        List representing the constructed CloudFormation GetAtt element.

    Raises
    ------
    CFBadNode
        If an invalid CloudFormation node is encountered.
    """

    if isinstance(node.value, str):
        return node.value.split(".", 1)
    elif isinstance(node.value, list):
        return [s.value for s in node.value]

    raise CFBadNode(f"Type <{type(node.value)}>")


CFLoader.add_multi_constructor("!", multi_constructor)


class Resource:
    def __init__(self, resource_id: str, resource: Dict[str, Any]) -> None:
        self.id = resource_id
        self.resource = resource


class EventSource(Resource):
    @property
    def type(self) -> EventType:
        return EventType(self.resource["Type"])

    @classmethod
    def from_resource(cls, resource_id: str, resource: Dict[str, Any]) -> "EventSource":
        event_sources = {
            EventType.API: ApiEvent,
            EventType.SQS: SQSEvent,
            EventType.SCHEDULE: ScheduleEvent,
        }

        event_type = EventType(resource["Type"])
        event_source = event_sources.get(event_type, cls)

        return event_source(resource_id, resource)


class ApiEvent(EventSource):
    @property
    def path(self):
        return self.resource["Properties"]["Path"]

    @property
    def method(self):
        return self.resource["Properties"]["Method"]

    @property
    def rest_api_id(self):
        resource_id = self.resource["Properties"]["RestApiId"]

        if isinstance(resource_id, dict):
            resource_id = resource_id["Ref"]

        return resource_id


class SQSEvent(EventSource):
    @property
    def queue(self) -> str:
        return self.resource["Properties"]["Queue"]

    @property
    def batch_size(self) -> int:
        return self.resource["Properties"]["BatchSize"]


class ScheduleEvent(EventSource):
    @property
    def schedule(self) -> str:
        return self.resource["Properties"]["Schedule"]


class Function(Resource):
    @property
    def name(self) -> str:
        return self.resource["Properties"]["FunctionName"]

    @property
    def handler(self) -> str:
        """
        Returns a string representing the full module path for a Lambda Function handler.
        The path is built by joining the code URI and the handler attributes on
        the CloudFormation for the given Lambda Function identified by resource_id.

        Returns
        -------
        str
            The constructed Lambda handler path.
        """

        if not hasattr(self, "_handler"):
            handler_path = self.resource["Properties"]["Handler"]
            code_uri = self.resource["Properties"].get("CodeUri")

            if code_uri:
                handler_path = f"{code_uri}.{handler_path}".replace("/", "")

            self._handler = handler_path

        return self._handler

    @property
    def environment(self) -> Dict[str, Union[str, Dict[str, Any]]]:
        """
        Returns a dictionary containing the environment variables for the Lambda Function.

        Returns
        -------
        Dict[str, str]
            The environment variables for the Lambda Function.
        """

        if not hasattr(self, "_environment"):
            self._environment = (
                self.resource["Properties"].get("Environment", {}).get("Variables", {})
            )

        return self._environment

    @property
    def events(self) -> Dict[str, EventSource]:
        if not hasattr(self, "_events"):
            self._events = {}
            events = self.resource["Properties"].get("Events", {})

            for resource_id, resource in events.items():
                self._events[resource_id] = EventSource.from_resource(resource_id, resource)

        return self._events

    def filtered_events(self, event_type: EventType) -> Dict[str, EventSource]:
        events = {}

        for id, event in self.events.items():
            if event.type == event_type:
                events[id] = event

        return events


class Api(Resource):
    @property
    def name(self) -> str:
        return self.resource["Properties"]["Name"]

    @property
    def stage_name(self) -> str:
        return self.resource["Properties"]["StageName"]


class Queue(Resource):
    @property
    def name(self) -> str:
        return self.resource["Properties"]["QueueName"]

    @property
    def visibility_timeout(self) -> int:
        return self.resource["Properties"]["VisibilityTimeout"]

    @property
    def message_retention_period(self) -> int:
        return self.resource["Properties"]["MessageRetentionPeriod"]

    @property
    def redrive_policy(self) -> Dict[str, Any]:
        return self.resource["Properties"]["RedrivePolicy"]


class Bucket(Resource):
    @property
    def name(self) -> str:
        return self.resource["Properties"]["BucketName"]


class CloudformationTemplate:
    """
    Represents an AWS CloudFormation template and provides methods for
    extracting information from the template.

    Parameters
    ----------
    template_path : Optional[str]
        Path to the CloudFormation template file.
    parameters : Optional[Dict[str, str]]
        Dictionary representing parameters name and default value.

    Attributes
    ----------
    template : Dict[str, Any]
        Dictionary representing the loaded CloudFormation template.
    """

    def __init__(
        self,
        template_path: Optional[str] = None,
        parameters: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initializes the CloudFormationTemplate object.
        """

        self.template = self.load(template_path)
        self.include_files()
        self.template = self.evaluate_and_replace(self.template)
        self.set_parameters(parameters)

    @property
    def functions(self) -> Dict[str, Function]:
        """
        Dict[str, Function]:
            Dictionary containing Lambda function resources in the CloudFormation template.
        """

        if not hasattr(self, "_functions"):
            self._functions = {}
            nodes = self.find_nodes(self.template["Resources"], ResourceType.FUNCTION)

            for resource_id, resource in nodes.items():
                self._functions[resource_id] = Function(resource_id, resource)

        return self._functions

    @property
    def apis(self) -> Dict[str, Api]:
        """
        Dict[str, Api]:
            Dictionary containing API Gateway resources in the CloudFormation template.
        """

        if not hasattr(self, "_apis"):
            self._apis = {}
            nodes = self.find_nodes(self.template["Resources"], ResourceType.API)

            for resource_id, resource in nodes.items():
                self._apis[resource_id] = Api(resource_id, resource)

        return self._apis

    @property
    def queues(self) -> Dict[str, Queue]:
        """
        Dict[str, Queue]:
            Dictionary containing SQS Queue resources in the CloudFormation template.
        """
        if not hasattr(self, "_queues"):
            self._queues = {}
            nodes = self.find_nodes(self.template["Resources"], ResourceType.QUEUE)

            for resource_id, resource in nodes.items():
                self._queues[resource_id] = Queue(resource_id, resource)

        return self._queues

    @property
    def buckets(self) -> Dict[str, Bucket]:
        """
        Dict[str, Bucket]:
            Dictionary containing buckets resources in the CloudFormation template.
        """
        if not hasattr(self, "_buckets"):
            self._buckets = {}
            nodes = self.find_nodes(self.template["Resources"], ResourceType.BUCKET)

            for resource_id, resource in nodes.items():
                self._buckets[resource_id] = Bucket(resource_id, resource)

        return self._buckets

    @property
    def environment(self) -> Dict[str, Any]:
        """
        Dict[str, Any]:
            Dictionary containing environment variables in the CloudFormation template.
        """

        if not hasattr(self, "_environment"):
            self._environment = self.find_environment()

        return self._environment

    def include_files(self):
        """
        Load external files specified in the CloudFormation template like OpenAPI schema.
        """

        for api in self.apis.values():
            # TODO: add definition body to the API object
            if "DefinitionBody" not in api.resource["Properties"]:
                continue

            lc = api.resource["Properties"]["DefinitionBody"]["Fn::Transform"]["Parameters"][
                "Location"
            ]

            with open(lc) as fp:
                swagger = yaml.safe_load(fp)

            api.resource["Properties"]["DefinitionBody"] = swagger

    def set_parameters(self, parameters: Optional[Dict[str, str]]) -> None:
        """
        Set the default value of parameters in the CloudFormation template.

        Parameters
        ----------
        parameters : Optional[Dict[str, str]]
            Dictionary representing parameters name and default value.
        """

        if "Parameters" not in self.template:
            return None

        params = parameters or {}

        for name, value in params.items():
            if name in self.template["Parameters"]:
                self.template["Parameters"][name]["Default"] = value

    def load(self, template: Optional[str] = None) -> Dict[str, Any]:
        """
        Reads CloudFormation template file from the disk and convert it to a dictionary.

        If the template argument is not set it is assumed an YAML file named
        template exists in the current directory.

        Parameters
        ----------
        template : Optional[str]
            Path to the CloudFormation template file.

        Returns
        -------
        Dict[str, Any]
            Dictionary representing the loaded CloudFormation template.

        Raises
        ------
        CFTemplateNotFound
            Exception raised when CloudFormation template file is not found.
        """

        path: Optional[Path] = None

        if isinstance(template, str):
            path = Path(template)
        else:
            paths = (Path("template.yml"), Path("template.yaml"))
            path_generator = (p for p in paths if p.is_file())
            path = next(path_generator, None)

        if path is None or not path.is_file():
            filename = template or "[template.yml, template.yaml]"
            raise CFTemplateNotFound(filename)

        with path.open() as fp:
            return yaml.load(fp, CFLoader)

    def find_nodes(
        self, tree: Dict[str, Any], node_type: Union[ResourceType, EventType]
    ) -> Dict[str, Any]:
        """
        Finds nodes of a specific type in the CloudFormation template.

        Parameters
        ----------
        tree : Dict[str, Any]
            Dictionary representing a subset of the CloudFormation template.
        node_type : NodeType
            The type of node to search for.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing nodes of the specified type.
        """

        nodes = {}

        for key, node in tree.items():
            if node["Type"] == node_type.value:
                nodes[key] = node

        return nodes

    def find_environment(self) -> Dict[str, Any]:
        """
        Reads the CloudFormation template to extract environment variables
        defined at both global and function levels.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing environment variables in the
            CloudFormation template.
        """
        variables = (
            self.template.get("Globals", {})
            .get("Function", {})
            .get("Environment", {})
            .get("Variables", {})
        )

        for function in self.functions.values():
            variables.update(function.environment)

        for key, value in variables.items():
            variables[key] = str(value)

        return variables

    def evaluate_and_replace(self, obj) -> Dict[str, Any]:
        import ipdb
        ipdb.set_trace()
        functions = [
            "Fn::Base64",
            "Fn::FindInMap",
            "Fn::GetAtt",
            "Fn::Join",
            "Fn::Select",
            "Fn::Split",
            "Fn::Sub",
            "Ref",
        ]

        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in functions:
                    obj[key] = IntrinsicFunctions.eval(obj, self.template)
                
                elif isinstance(value, dict):
                    obj[key] = self.evaluate_and_replace(value)

            return obj

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    for key, value in item.items():
                        if key in functions:
                            obj[i] = IntrinsicFunctions.eval(obj, self.template)
                        
                        elif isinstance(value, dict):
                            obj[i] = self.evaluate_and_replace(item)

                elif isinstance(item, str) and item.startswith("!"):
                    obj[i] = IntrinsicFunctions.eval(item, self.template)
                
            return obj


class IntrinsicFunctions:
    """
    Resolve intrinsic functions in CloudFormation
    """

    @staticmethod
    def eval(function: Dict[str, Any], template: Dict[str, Any]) -> Any:
        """
        Try to resolve an intrinsic function.

        Parameters
        ----------
        function : Dict[str, Any]
            The intrinsic function and its arguments.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Any
            The result of the intrinsic function, or None if it cannot access
            the value.

        Raises
        ------
        NotImplementedError
            If the intrinsic function is not implemented.
        """
        functions = {
            "Fn::Base64": IntrinsicFunctions.base64,
            "Fn::FindInMap": IntrinsicFunctions.find_in_map,
            "Fn::GetAtt": IntrinsicFunctions.get_att,
            "Fn::Join": IntrinsicFunctions.join,
            "Fn::Select": IntrinsicFunctions.select,
            "Fn::Split": IntrinsicFunctions.split,
            "Fn::Sub": IntrinsicFunctions.sub,
            "Ref": IntrinsicFunctions.ref,
        }

        fun, val = list(function.items())[0]

        if fun in functions.keys():
            return functions[fun](val, template)
        else:
            logging.warning(f"{fun} intrinsic function not implemented")
            return None

    @staticmethod
    def base64(value: str, template: Dict[str, Any]) -> str:
        """
        Encode a string to base64.

        Parameters
        ----------
        value : str
            The string to be encoded to base64.

        Returns
        -------
        str
            The base64-encoded string.
        """
        return base64.b64encode(value.encode()).decode()

    @staticmethod
    def find_in_map(value: List[Any], template: Dict[str, Any]) -> Any:
        """
        Gets a value from a mapping declared in the CloudFormation
        template.

        Parameters
        ----------
        value : List[Any]
            List containing the map name, top-level key, and second-level key.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Any
            The value from the map, or None if the map or keys are not found.
        """
        map_name, top_level_key, second_level_key = value

        if map_name not in template.get("Mappings", {}):
            return None

        if isinstance(top_level_key, dict):
            top_level_key = IntrinsicFunctions.eval(top_level_key, template)

            if top_level_key is None:
                return None

        if top_level_key not in template["Mappings"][map_name]:
            return None

        return template["Mappings"][map_name][top_level_key].get(second_level_key)

    @staticmethod
    def ref(value: str, template: Dict[str, Any]) -> Optional[str]:
        """
        Gets a referenced value from the CloudFormation template.

        Parameters
        ----------
        value : str
            The name of the referenced value to retrieve.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Optional[str]
            The referenced value, or None if the reference is not found.
        """
        if value in template.get("Parameters", {}):
            resource = template["Parameters"][value]
            return resource.get("Default")
        # NOTE: this is a partial implementation

        return None

    @staticmethod
    def get_att(value: Union[List[str], str], template: Dict[str, Any]) -> Optional[str]:
        """
        Gets the value of an attribute from a CloudFormation template based on a list
        of logical name and attribute name.

        Parameters
        ----------
        value : List[Any]
            List containing the logical name and attribute name
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Optional[str]
            The value of atribute name, or None if the keys are not found.
        """
        if isinstance(value, str):
            value = value.split(".")

        logical_name, attribute_name = value

        if logical_name not in template["Resources"]:
            return None

        if isinstance(attribute_name, dict):
            attribute_name = IntrinsicFunctions.eval(attribute_name, template)

            if attribute_name is None:
                return None

        if attribute_name not in template["Resources"][logical_name]["Properties"]:
            return None

        attribute_value = template["Resources"][logical_name]["Properties"][attribute_name]

        if isinstance(attribute_value, dict):
            attribute_value = IntrinsicFunctions.eval(attribute_value, template)

            if attribute_value is None:
                return None

        return attribute_value

    @staticmethod
    def join(value: List[Any], template: Dict[str, Any]) -> Optional[str]:
        """
        Joins elements in a list with a specified delimiter.

        Parameters
        ----------
        value : List[Any]
            A list containing two elements: the delimiter as the first element,
            and the values to join as the second element.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Optional[str]
            The joined string if successful; otherwise, None.
        """
        delimiter, values = value

        for index, element in enumerate(values):
            if isinstance(element, dict):
                element = IntrinsicFunctions.eval(element, template)

            if element is None:
                return None

            values[index] = element

        return delimiter.join(values)

    @staticmethod
    def select(value: List[Any], template: Dict[str, Any]) -> Optional[str]:
        """
        Selects a value from a list based on the given index. If the value at the index
        is a dictionary, it evaluates it using CloudFormation template data.
        Parameters
        ----------
        value : List[Any]
            A list containing values from which to select.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.
        Returns
        -------
        Optional[str]
            The selected value from the list, or None if any of the evaluated
            values are None.
        """
        index, objects = value

        if isinstance(index, dict):
            index = IntrinsicFunctions.eval(index, template)

            if index is None:
                return None

        if isinstance(objects, dict):
            objects = IntrinsicFunctions.eval(objects, template)

            if objects is None:
                return None
        else:
            for i, obj in enumerate(objects):
                if isinstance(obj, dict):
                    objects[i] = IntrinsicFunctions.eval(obj, template)

                    if objects[i] is None:
                        return None

        return objects[int(index)]

    @staticmethod
    def split(value: List[Any], template: Dict[str, Any]) -> Optional[str]:
        """
        Splits a list of values using a specified delimiter.

        Parameters
        ----------
        value : List[Any]
            A tuple containing the delimiter as its first element, followed
            by a list of values to split.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Optional[str]
            A list of strings resulting from splitting using the delimiter.
            or None if any of the evaluated values are None.
        """
        delimiter, source = value

        if isinstance(source, dict):
            source = IntrinsicFunctions.eval(source, template)

            if source is None:
                return None

        return source.split(delimiter)

    def replace_placeholders(string: str, matches: List[Any]):
        pseudo_parameters = [
            "AWS::AccountId",
            "AWS::NotificationARNs",
            "AWS::NoValue",
            "AWS::Partition",
            "AWS::Region",
            "AWS::StackId",
            "AWS::StackName",
            "AWS::URLSuffix",
        ]

        result_string = string

        for match in matches:
            if match in pseudo_parameters:
                if match.replace("::", "_") in os.environ:
                    env_var = os.environ[match.replace("::", "_")]
                    result_string = result_string.replace(f"${{{match}}}", env_var)
                else:
                    return None
            else:
                if match in os.environ:
                    env_var = os.environ[match]
                    result_string = result_string.replace(f"${{{match}}}", env_var)
                else:
                    return None

        return result_string

    @staticmethod
    def sub(value: List[Any], template: Dict[str, Any]) -> Optional[str]:
        """
        Substitutes intrinsic functions and environment variables in the given value.

        Parameters
        ----------
        value : List[Any]
            A list containing the string to perform substitutions on and a dictionary
            containing variable names and their corresponding values.
        template : Dict[str, Any]
            A dictionary representing the CloudFormation template.

        Returns
        -------
        Optional[str]
            The resulting string after performing substitutions, or None if any of the
            variables or intrinsic functions could not be resolved.
        """
        pattern = r"\${(.*?)}"

        if isinstance(value, list):
            string, var_list = value

            for var_dict in var_list:
                var_name, var_value = list(var_dict.items())[0]

                if isinstance(var_name, dict):
                    var_name = IntrinsicFunctions.eval(var_name, template)

                    if var_name is None:
                        return None

                if isinstance(var_value, dict):
                    var_value = IntrinsicFunctions.eval(var_value, template)

                    if var_value is None:
                        return None

                if var_name in string:
                    result = string.replace(f"${{{var_name}}}", str(var_value))
                else:
                    return None

            matches = re.findall(pattern, result)

            if not matches:
                return result

            return IntrinsicFunctions.replace_placeholders(result, matches)
        else:
            matches = re.findall(pattern, value)

            return IntrinsicFunctions.replace_placeholders(value, matches)
