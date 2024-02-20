from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PREFIX = "Fn::"
WITHOUT_PREFIX = ("Ref", "Condition")


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
    API_EVENT : str
        Represents the "Api" node type.
    """

    API_GATEWAY = "AWS::Serverless::Api"
    LAMBDA = "AWS::Serverless::Function"
    API_EVENT = "Api"
    SQS_EVENT = "SQS"


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

    Attributes
    ----------
    template : Dict[str, Any]
        Dictionary representing the loaded CloudFormation template.
    """

    def __init__(self, template_path: Optional[str] = None) -> None:
        """
        Initializes the CloudFormationTemplate object.
        """

        self.template = self.load(template_path)
        self.include_files()

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

        code_uri = self.functions[resource_id]["Properties"]["CodeUri"]
        handler = self.functions[resource_id]["Properties"]["Handler"]
        handler_path = f"{code_uri}.{handler}".replace("/", "")
        return handler_path
