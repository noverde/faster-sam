import base64
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class NodeType(Enum):
    """
    Enum representing different types of CloudFormation nodes.

    Attributes
    ----------
    API_GATEWAY : str
        Represents the "AWS::Serverless::Api" node type.
    LAMBDA : str
        Represents the "AWS::Serverless::Function" node type.
    QUEUE : str
        Represents the "AWS::SQS::Queue" node type.
    API_EVENT : str
        Represents the "Api" node type.
    SCHEDULER_EVENT : str
        Represents the "Schedule" node type.
    """

    API_GATEWAY = "AWS::Serverless::Api"
    LAMBDA = "AWS::Serverless::Function"
    QUEUE = "AWS::SQS::Queue"
    API_EVENT = "Api"
    SQS_EVENT = "SQS"
    SCHEDULER_EVENT = "Schedule"


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
        self, template_path: Optional[str] = None, parameters: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Initializes the CloudFormationTemplate object.
        """

        self.template = self.load(template_path)
        self.include_files()
        self.set_parameters(parameters)

    @property
    def functions(self) -> Dict[str, Any]:
        """
        Dict[str, Any]:
            Dictionary containing Lambda function resources in the CloudFormation template.
        """

        if not hasattr(self, "_functions"):
            self._functions = self.find_nodes(self.template["Resources"], NodeType.LAMBDA)
        return self._functions

    @property
    def gateways(self) -> Dict[str, Any]:
        """
        Dict[str, Any]:
            Dictionary containing API Gateway resources in the CloudFormation template.
        """

        if not hasattr(self, "_gateways"):
            self._gateways = self.find_nodes(self.template["Resources"], NodeType.API_GATEWAY)
        return self._gateways

    @property
    def queues(self) -> Dict[str, Any]:
        """
        Dict[str, Any]:
            Dictionary containing SQS Queue resources in the CloudFormation template.
        """

        if not hasattr(self, "_queues"):
            self._queues = self.find_nodes(self.template["Resources"], NodeType.QUEUE)
        return self._queues

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

        for gateway in self.gateways.values():
            if "DefinitionBody" not in gateway["Properties"]:
                continue

            lc = gateway["Properties"]["DefinitionBody"]["Fn::Transform"]["Parameters"]["Location"]

            with open(lc) as fp:
                swagger = yaml.safe_load(fp)

            gateway["Properties"]["DefinitionBody"] = swagger

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

    def find_nodes(self, tree: Dict[str, Any], node_type: NodeType) -> Dict[str, Any]:
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
            if "Variables" in function.get("Properties", {}).get("Environment", {}):
                variables.update(function["Properties"]["Environment"]["Variables"])

        environment = {}

        for key, val in variables.items():
            if isinstance(val, (str, int, float)):
                environment[key] = str(val)
            else:
                value = IntrinsicFunctions.eval(val, self.template)
                if value is not None:
                    environment[key] = str(value)

        return environment

    def lambda_handler(self, resource_id: str) -> str:
        """
        Returns a string representing the full module path for a Lambda Function handler.
        The path is built by joining the code URI and the handler attributes on
        the CloudFormation for the given Lambda Function identified by resource_id.
        Parameters
        ----------
        resource_id : str
            The id of the Lambda function resource.
        Returns
        -------
        str
            The constructed Lambda handler path.
        """

        handler_path = self.functions[resource_id]["Properties"]["Handler"]
        code_uri = self.functions[resource_id]["Properties"].get("CodeUri")

        if code_uri:
            handler_path = f"{code_uri}.{handler_path}".replace("/", "")

        return handler_path


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
        implemented = (
            "Fn::Base64",
            "Fn::FindInMap",
            "Ref",
            "Fn::GetAtt",
            "Fn::Join",
            "Fn::Select",
            "Fn::Split",
        )

        if isinstance(function, list):
            import ipdb

            ipdb.set_trace()
        fun, val = list(function.items())[0]

        if fun not in implemented:
            logging.warning(f"{fun} intrinsic function not implemented")

        if "Fn::Base64" == fun:
            return IntrinsicFunctions.base64(val)

        if "Fn::FindInMap" == fun:
            return IntrinsicFunctions.find_in_map(val, template)

        if "Fn::GetAtt" == fun:
            return IntrinsicFunctions.get_att(val, template)

        if "Fn::Join" == fun:
            return IntrinsicFunctions.join(val, template)

        if "Fn::Select" == fun:
            return IntrinsicFunctions.select(val, template)

        if "Fn::Split" == fun:
            return IntrinsicFunctions.split(val, template)

        if "Ref" == fun:
            return IntrinsicFunctions.ref(val, template)

        return None

    @staticmethod
    def base64(value: str) -> str:
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
    def get_att(value: List[Any], template: Dict[str, Any]) -> Optional[str]:
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
        logical_name, attribute_name = value

        if logical_name not in template["Resources"]:
            return None

        if isinstance(attribute_name, dict):
            attribute_name = IntrinsicFunctions.eval(attribute_name, template)

            if attribute_name is None:
                return None

        if attribute_name not in template["Resources"][logical_name]["Properties"]:
            return None

        function_value = template["Resources"][logical_name]["Properties"][attribute_name]

        if isinstance(function_value, dict):
            function_value = IntrinsicFunctions.eval(function_value, template)

            if function_value is None:
                return None

        return function_value

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

        if len(values) < 2:
            return None

        for i in range(len(values)):
            if isinstance(values[i], dict):
                evaluated_value = IntrinsicFunctions.eval(values[i], template)

                if evaluated_value is None:
                    return None

                values[i] = evaluated_value

        return delimiter.join(value[1])

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
        index, values = value

        if isinstance(index, dict):
            index = IntrinsicFunctions.eval(index, template)

            if index is None:
                return None

        if isinstance(values, dict):
            values = IntrinsicFunctions.eval(values, template)

            if values is None:
                return None

        result = []

        for i in range(len(values)):
            if isinstance(values[i], dict):
                evaluated_value = IntrinsicFunctions.eval(values[i], template)

                if evaluated_value is None:
                    return None

                result.append(evaluated_value)
            else:
                result.append(values[i])

        return result[int(index)]

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
        delimiter, value = value

        result = []

        if isinstance(value, dict):
            value = IntrinsicFunctions.eval(value, template)

            if value is None:
                return None

        split_parts = value.split(delimiter)

        for part in split_parts:
            result.append(part)

        return result
