from typing import Any, Callable, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


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
