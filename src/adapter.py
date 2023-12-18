import re
from typing import Any, Dict, Optional

from fastapi import FastAPI

from cloudformation import CloudformationTemplate, NodeType
from openapi import custom_openapi
from routing import APIRoute

ARN_PATTERN = r"^arn:aws:apigateway.*\${(\w+)\.Arn}/invocations$"


class GatewayLookupError(LookupError):
    pass


class SAM:
    def __init__(self, template_path: Optional[str] = None) -> None:
        self.template = CloudformationTemplate(template_path)

    def configure_api(self, app: FastAPI, gateway_id: Optional[str] = None) -> None:
        gateway: Dict[str, Any] = {"Properties": {}}

        if gateway_id is not None:
            gateway = self.template.gateways[gateway_id]
        else:
            gateway_ids = list(self.template.gateways.keys())
            gateway_len = len(gateway_ids)

            if gateway_len > 1:
                ids = ", ".join(gateway_ids)
                raise GatewayLookupError(f"Missing required gateway ID. Found: {ids}")

            if gateway_len == 1:
                gateway_id = gateway_ids[0]
                gateway = self.template.gateways[gateway_id]

        openapi_schema = gateway["Properties"].get("DefinitionBody")

        if openapi_schema is None:
            routes = self.lambda_mapper(gateway_id)
        else:
            routes = self.openapi_mapper(openapi_schema)
            app.openapi = custom_openapi(app, openapi_schema)

        self.register_routes(app, routes)

    def openapi_mapper(self, openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        routes: Dict[str, Any] = {}

        for path, methods in openapi_schema["paths"].items():
            for method, info in methods.items():
                if "x-amazon-apigateway-integration" not in info:
                    continue

                uri = info["x-amazon-apigateway-integration"]["uri"]["Fn::Sub"]
                match = re.match(ARN_PATTERN, uri)

                if not match:
                    continue

                resource_id = match.group(1)
                function = self.template.functions[resource_id]
                handler_path = self.lambda_handler(function["Properties"])
                endpoint = {method: {"handler": handler_path}}

                routes.setdefault(path, {}).update(endpoint)

        return routes

    def lambda_mapper(self, gateway_id: Optional[str]) -> Dict[str, Any]:
        routes: Dict[str, Any] = {}

        for function in self.template.functions.values():
            if "Events" not in function["Properties"]:
                continue

            handler_path = self.lambda_handler(function["Properties"])
            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.API_EVENT)

            for event in events.values():
                rest_api_id = event["Properties"].get("RestApiId", {"Ref": None})["Ref"]

                if rest_api_id != gateway_id:
                    continue

                path = event["Properties"]["Path"]
                method = event["Properties"]["Method"]
                endpoint = {method: {"handler": handler_path}}

                routes.setdefault(path, {}).update(endpoint)

        return routes

    def lambda_handler(self, function: Dict[str, Any]) -> str:
        code_uri = function["CodeUri"]
        handler = function["Handler"]
        handler_path = f"{code_uri}.{handler}".replace("/", "")

        return handler_path

    def register_routes(self, app: FastAPI, routes: Dict[str, Any]) -> None:
        for path, methods in routes.items():
            for method, config in methods.items():
                app.router.add_api_route(
                    path,
                    config["handler"],
                    methods=[method],
                    route_class_override=APIRoute,
                )
