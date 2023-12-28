from typing import Any, Callable, Dict, List

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI, openapi_schema: Dict[str, Any]) -> Callable[[], Dict[str, Any]]:
    """
    Custom OpenAPI generator for the FastAPI application.

    Parameters
    ----------
    app : FastAPI
        The FastAPI application instance.
    openapi_schema : Dict[str, Any]
        OpenAPI schema to be merged with the new one.

    Returns
    -------
    Callable[[], Dict[str, Any]]
        A callable function that generates the OpenAPI schema.

    e.g

    >>> schema = json.load(open("swagger.json"))
    >>> app = FastAPI()
    >>> app.openapi = custom_openapi(app, schema)
    """

    def openapi() -> Dict[str, Any]:
        """
        Generates the merged OpenAPI schema.

        Returns
        -------
        Dict[str, Any]
            The merged OpenAPI schema.
        """

        if app.openapi_schema is not None:
            return app.openapi_schema

        fastapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            servers=app.servers,
        )

        servers: List[Dict[str, Any]] = fastapi_schema.get("servers", [])
        servers.extend(openapi_schema.get("servers", []))

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

        app.openapi_schema = {**openapi_schema, "servers": servers, "paths": paths}
        app.openapi_schema["components"] = components

        return app.openapi_schema

    return openapi
