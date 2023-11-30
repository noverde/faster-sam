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


def find_nodes(tree: Dict[str, Any], node_type: NodeType) -> List[Dict[str, Any]]:
    nodes = []

    for id_, properties in tree.items():
        if properties["Type"] == node_type.value:
            nodes.append({id_: properties})

    return nodes


class Template:
    def __init__(self, template: Optional[str] = None) -> None:
        self._template = self.load(template)
        self._gateways = None

    @property
    def template(self):
        return self._template

    @property
    def gateways(self):
        if not self._gateways:
            self._gateways = find_nodes(self._template["Resources"], NodeType.API_GATEWAY)
        return self._gateways

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
