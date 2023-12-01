from typing import Any, Dict, Optional

from fastapi import FastAPI

from cloudformation import CloudformationTemplate, NodeType


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
        self.template = CloudformationTemplate(template_path)
        self.route_mapping()

    def route_mapping(self) -> None:
        self.routes: Dict[str, Any] = {gateway["Id"]: dict() for gateway in self.template.gateways}
        self.routes["ImplicitGateway"] = {}

        for function in self.template.functions:
            if "Events" not in function["Properties"]:
                continue

            code_uri = function["Properties"]["CodeUri"]
            handler = function["Properties"]["Handler"]
            handler_path = f"{code_uri}.{handler}".replace("/", "")

            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.API)

            for event in events:
                path = event["Properties"]["Path"]
                method = event["Properties"]["Method"]
                endpoint = {method: {"handler": handler_path}}
                gateway = "ImplicitGateway"

                if "RestApiId" in event["Properties"]:
                    gateway = event["Properties"]["RestApiId"]["Ref"]

                self.routes[gateway].setdefault(path, {}).update(endpoint)
