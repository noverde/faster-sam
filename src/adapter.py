import re
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from cloudformation import CloudformationTemplate, NodeType
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
                handler_path = self.template.lambda_handler(resource_id)
                endpoint = {method: {"handler": handler_path}}

                routes.setdefault(path, {}).update(endpoint)

        return routes

    def lambda_mapper(self, gateway_id: Optional[str]) -> Dict[str, Any]:
        routes: Dict[str, Any] = {}

        for resource_id, function in self.template.functions.items():
            if "Events" not in function["Properties"]:
                continue

            handler_path = self.template.lambda_handler(resource_id)
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

    def register_routes(self, app: FastAPI, routes: Dict[str, Any]) -> None:
        for path, methods in routes.items():
            for method, config in methods.items():
                app.router.add_api_route(
                    path,
                    config["handler"],
                    methods=[method],
                    route_class_override=APIRoute,
                )


def custom_openapi(app: FastAPI, openapi_schema: Dict[str, Any]) -> Callable[[], Dict[str, Any]]:
    def openapi() -> Dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        fastapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
        )

        paths = {**fastapi_schema["paths"], **openapi_schema["paths"]}

        openapi_components = openapi_schema.get("components", {})
        openapi_schemas = openapi_components.get("schemas", {})
        openapi_security_schemes = openapi_components.get("securitySchemes", {})
        openapi_examples = openapi_components.get("examples", {})

        fastapi_components = fastapi_schema.get("components", {})
        fastapi_schemas = fastapi_components.get("schemas", {})
        fastapi_security_schemes = fastapi_components.get("securitySchemes", {})
        fastapi_examples = fastapi_components.get("examples", {})

        schemas = {**fastapi_schemas, **openapi_schemas}
        security_schemas = {**fastapi_security_schemes, **openapi_security_schemes}
        examples = {**fastapi_examples, **openapi_examples}

        components = {}

        if schemas:
            components["schemas"] = schemas

        if security_schemas:
            components["securitySchemes"] = security_schemas

        if examples:
            components["examples"] = examples

        app.openapi_schema = {**openapi_schema, "paths": paths}
        app.openapi_schema["components"] = components

        return app.openapi_schema

    return openapi
