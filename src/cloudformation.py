import re
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


def load(template: Optional[str] = None) -> Dict[str, Any]:
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


def list_functions(template: Dict[str, any]):
    functions = {}
    resources = template["Resources"]

    for name, conf in resources.items():
        if conf["Type"] == "AWS::Serverless::Function":
            functions[name] = conf

    return functions


def padronize_name(camel_string: str) -> str:
    formated = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_string).lower()
    return formated


def get_handler(properties):
    code_uri = properties["CodeUri"].replace("/", "")

    handler = properties["Handler"]

    module, name_handler = handler.rsplit(".", maxsplit=1)

    path = f"{code_uri}.{module}"

    module_handler = __import__(path, fromlist=(name_handler,))

    return getattr(module_handler, name_handler)


def build_routes(template):
    functions = list_functions(template)

    routes = {}

    for name, conf in functions.items():
        properties = conf["Properties"]

        for event_details in properties["Events"].values():
            if event_details["Type"] == "Api":
                api = event_details["Properties"]

                if "RestApiId" in api and "Ref" in api["RestApiId"]:
                    api_gateway = api["RestApiId"]["Ref"]
                else:
                    api_gateway = "DefaultApiGateway"

                routes.setdefault(api_gateway, {})

                endpoint_method = {
                    api["Method"].upper(): {
                        "name": padronize_name(properties.get("FunctionName", name)),
                        "handler": get_handler(properties),
                    }
                }

                if api["Path"] in routes[api_gateway]:
                    routes[api_gateway][api["Path"]].update(endpoint_method)
                else:
                    routes[api_gateway][api["Path"]] = endpoint_method

    return routes
