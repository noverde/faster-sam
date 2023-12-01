from typing import Any, Dict, Optional

from fastapi import FastAPI

from cloudformation import CloudformationTemplate, NodeType


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
        self.template = CloudformationTemplate(template_path)
        self.route_mapping()

    def route_mapping(self) -> None:
        self.routes: Dict[str, Any] = {key: dict() for key in self.template.gateways.keys()}
        self.routes["ImplicitGateway"] = {}
        self.lambda_mapper()

    def lambda_mapper(self):
        for function in self.template.functions.values():
            if "Events" not in function["Properties"]:
                continue

            code_uri = function["Properties"]["CodeUri"]
            handler = function["Properties"]["Handler"]
            handler_path = f"{code_uri}.{handler}".replace("/", "")

            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.API)

            for event in events.values():
                path = event["Properties"]["Path"]
                method = event["Properties"]["Method"]
                endpoint = {method: {"handler": handler_path}}
                gateway = "ImplicitGateway"

                if "RestApiId" in event["Properties"]:
                    gateway = event["Properties"]["RestApiId"]["Ref"]

                self.routes[gateway].setdefault(path, {}).update(endpoint)
