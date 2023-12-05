import re
from typing import Any, Dict, Optional

from fastapi import FastAPI

from cloudformation import CloudformationTemplate, NodeType

ARN_PATTERN = r"^arn:aws:apigateway.*\${(\w+)\.Arn}/invocations$"


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
        self.template = CloudformationTemplate(template_path)
        self.route_mapping()

    def route_mapping(self) -> None:
        self.routes: Dict[str, Any] = {key: dict() for key in self.template.gateways.keys()}
        self.routes["ImplicitGateway"] = {}
        self.openapi_mapper()
        self.lambda_mapper()

    def openapi_mapper(self) -> None:
        for id, gateway in self.template.gateways.items():
            self.routes[id] = {}

            if "DefinitionBody" not in gateway["Properties"]:
                continue

            openapi = gateway["Properties"]["DefinitionBody"]

            for path, methods in openapi["paths"].items():
                for method, info in methods.items():
                    if "x-amazon-apigateway-integration" not in info:
                        continue

                    uri = info["x-amazon-apigateway-integration"]["uri"]["Fn::Sub"]
                    match = re.match(ARN_PATTERN, uri)

                    if not match:
                        continue

                    arn = match.group(1)
                    func = self.template.functions[arn]

                    if func is None:
                        continue

                    # Cache function ARN

                    handler_path = self.lambda_handler(func["Properties"])

                    endpoint = {method: {"handlers": handler_path}}

                    self.routes[id].setdefault(path, {}).update(endpoint)

    def lambda_mapper(self):
        for function in self.template.functions.values():
            if "Events" not in function["Properties"]:
                continue

            handler_path = self.lambda_handler(function["Properties"])

            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.API_EVENT)

            for event in events.values():
                path = event["Properties"]["Path"]
                method = event["Properties"]["Method"]
                endpoint = {method: {"handler": handler_path}}
                gateway = "ImplicitGateway"

                if "RestApiId" in event["Properties"]:
                    gateway = event["Properties"]["RestApiId"]["Ref"]

                self.routes[gateway].setdefault(path, {}).update(endpoint)

    def lambda_handler(self, function: Dict[str, Any]) -> str:
        code_uri = function["CodeUri"]
        handler = function["Handler"]
        handler_path = f"{code_uri}.{handler}".replace("/", "")

        return handler_path
