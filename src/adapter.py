from typing import Any, Dict, Optional

from fastapi import FastAPI

from cloudformation import CloudformationTemplate, NodeType
from routing import APIRoute


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
        self.template = CloudformationTemplate(template_path)
        self.route_mapping()

    def route_mapping(self) -> None:
        self.routes: Dict[str, Any] = {key: dict() for key in self.template.gateways.keys()}
        self.routes["ImplicitGateway"] = {}
        self.lambda_mapper()
        self.register_routes()

    def lambda_mapper(self):
        for function in self.template.functions.values():
            if "Events" not in function["Properties"]:
                continue

            handler_path = self.lambda_handler(function["Properties"])

            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.API)

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

    def register_routes(self):
        # TODO: support multiple API Gateways
        for paths in self.routes.values():
            if not paths:
                continue

            for path, methods in paths.items():
                for method, config in methods.items():
                    self.app.router.add_api_route(
                        path,
                        config["handler"],
                        methods=[method],
                        route_class_override=APIRoute,
                    )
