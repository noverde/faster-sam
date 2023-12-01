from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PREFIX = "Fn::"
WITHOUT_PREFIX = ("Ref", "Condition")


class CFTemplateNotFound(FileNotFoundError):
    pass


class CFBadTag(TypeError):
    pass


class CFBadNode(ValueError):
    pass


class CFLoader(yaml.SafeLoader):
    pass


class NodeType(Enum):
    API_GATEWAY = "AWS::Serverless::Api"
    LAMBDA = "AWS::Serverless::Function"
    API = "Api"


def multi_constructor(loader: CFLoader, tag_suffix: str, node: yaml.nodes.Node) -> Dict[str, Any]:
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
    if isinstance(node.value, str):
        return node.value.split(".", 1)
    elif isinstance(node.value, list):
        return [s.value for s in node.value]

    raise CFBadNode(f"Type <{type(node.value)}>")


CFLoader.add_multi_constructor("!", multi_constructor)


class CloudformationTemplate:
    def __init__(self, template_path: Optional[str] = None) -> None:
        self.template = self.load(template_path)

    @property
    def functions(self) -> Dict[str, Any]:
        if not hasattr(self, "_functions"):
            self._functions = self.find_nodes(self.template["Resources"], NodeType.LAMBDA)
        return self._functions

    @property
    def gateways(self) -> Dict[str, Any]:
        if not hasattr(self, "_gateways"):
            self._gateways = self.find_nodes(self.template["Resources"], NodeType.API_GATEWAY)
            self.load_files()
        return self._gateways

    def load_files(self):
        for gateway in self._gateways.values():
            try:
                file = gateway["Properties"]["DefinitionBody"]["Fn::Transform"]["Parameters"][
                    "Location"
                ]
            except KeyError:
                continue

        with open(file) as fp:
            swagger = yaml.load(fp)

        gateway["Properties"]["DefinitionBody"] = swagger

    def load(self, template: Optional[str] = None) -> Dict[str, Any]:
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
        nodes = {}

        for key, node in tree.items():
            if node["Type"] == node_type.value:
                nodes[key] = node

        return nodes
