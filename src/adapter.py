import re
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from cloudformation import CloudformationTemplate, NodeType
from routing import APIRoute

ARN_PATTERN = r"^arn:aws:apigateway.*\${(\w+)\.Arn}/invocations$"


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
        self.openapi = None
        self.template = CloudformationTemplate(template_path)
        self.route_mapping()
        app.openapi = custom_openapi(app, self.openapi)

    def route_mapping(self) -> None:
        self.routes: Dict[str, Any] = {key: dict() for key in self.template.gateways.keys()}
        self.routes["ImplicitGateway"] = {}
        self._mapped_functions = set()
        self.openapi_mapper()
        self.lambda_mapper()
        self.register_routes()

    def openapi_mapper(self) -> None:
        for id, gateway in self.template.gateways.items():
            self.routes[id] = {}

            if "DefinitionBody" not in gateway["Properties"]:
                continue

            openapi = gateway["Properties"]["DefinitionBody"]

            self.openapi = openapi

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

                    self._mapped_functions |= {arn}

                    handler_path = self.lambda_handler(func["Properties"])

                    endpoint = {method: {"handler": handler_path}}

                    self.routes[id].setdefault(path, {}).update(endpoint)

    def lambda_mapper(self):
        for id, function in self.template.functions.items():
            if "Events" not in function["Properties"] or id in self._mapped_functions:
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


def custom_openapi(app, openapi_schema):
    def openapi():
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

        app.openapi_schema = {**openapi_schema, "paths": paths}

        components = {}

        if schemas:
            components["schemas"] = schemas

        if security_schemas:
            components["securitySchemes"] = security_schemas

        if examples:
            components["examples"] = examples

        app.openapi_schema["components"] = components

        return app.openapi_schema

    return openapi
