from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


class CustomOpenAPI:
    def __init__(self, app: FastAPI, openapi_schema: Dict[str, Any]) -> None:
        self.app = app
        self.openapi_schema = openapi_schema

    def __call__(self) -> Dict[str, Any]:
        if self.app.openapi_schema is not None:
            return self.app.openapi_schema

        fastapi_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            summary=self.app.summary,
            description=self.app.description,
            routes=self.app.routes,
        )

        paths = {**fastapi_schema["paths"], **self.openapi_schema["paths"]}

        openapi_components = self.openapi_schema.get("components", {})
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

        self.app.openapi_schema = {**self.openapi_schema, "paths": paths}
        self.app.openapi_schema["components"] = components

        return self.app.openapi_schema
