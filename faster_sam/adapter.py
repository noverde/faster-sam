import re
from typing import Any, Dict, Optional

from fastapi import FastAPI

from faster_sam.cloudformation import CloudformationTemplate, NodeType
from faster_sam.openapi import custom_openapi
from faster_sam.routing import APIRoute

ARN_PATTERN = r"^arn:aws:apigateway.*\${(\w+)\.Arn}/invocations$"


class GatewayLookupError(LookupError):
    """
    Exception for errors related to Gateway.
    """

    pass


class SAM:
    """
    SAM class to run AWS SAM applications with FastAPI.

    ...

    Parameters
    ----------
    template_path : Optional[str]
        Path to the CloudFormation template file.

    Attributes
    ----------
    template : CloudformationTemplate
        Instance of CloudformationTemplate based on the provided template_path.

    Methods
    -------
    configure_api(app: FastAPI, gateway_id: Optional[str] = None) -> None:
        Configures the FastAPI app with routes based on the template file.

    openapi_mapper(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        Maps OpenAPI schema with FastAPI routes.

    lambda_mapper(gateway_id: Optional[str]) -> Dict[str, Any]:
        Maps Lambda functions associated with an API Gateway to FastAPI routes.

    register_routes(app: FastAPI, routes: Dict[str, Any]) -> None:
        Registers FastAPI routes based on the provided routes dictionary.
    """

    def __init__(self, template_path: Optional[str] = None) -> None:
        """
        Initializes the SAM object.

        Parameters
        ----------
        template_path : Optional[str]
            Path to the CloudFormation template file.
        """

        self.template = CloudformationTemplate(template_path)

    def configure_api(self, app: FastAPI, gateway_id: Optional[str] = None) -> None:
        """
        Configures the FastAPI app with routes based on the template file.

        Parameters
        ----------
        app : FastAPI
            The FastAPI app instance to be configured.
        gateway_id : Optional[str], optional
            Optional gateway ID to filter the routes for a specific API Gateway.

        Raises
        ------
        GatewayLookupError
            Any error related to gateway, like missing the gateway id.
        """

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
        """
        Maps OpenAPI schema with OpenAPI format routes.

        Parameters
        ----------
        openapi_schema : Dict[str, Any]
            OpenAPI schema dictionary.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing FastAPI routes.
        """

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
        """
        Maps Lambda functions associated with an API Gateway to OpenAPI format routes.

        Parameters
        ----------
        gateway_id : Optional[str]
            Optional gateway ID to filter the routes for a specific API Gateway.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing FastAPI routes.
        """

        routes: Dict[str, Any] = {}

        for resource_id, function in self.template.functions.items():
            if "Events" not in function["Properties"]:
                continue

            handler_path = self.template.lambda_handler(resource_id)
            events = self.template.find_nodes(
                function["Properties"]["Events"], NodeType.API_EVENT
            )

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
        """
        Registers FastAPI routes based on the provided routes dictionary.

        Parameters
        ----------
        app : FastAPI
            The FastAPI app instance.
        routes : Dict[str, Any]
            Dictionary containing FastAPI routes.
        """

        for path, methods in routes.items():
            for method, config in methods.items():
                app.router.add_api_route(
                    path,
                    config["handler"],
                    methods=[method],
                    route_class_override=APIRoute,
                )
