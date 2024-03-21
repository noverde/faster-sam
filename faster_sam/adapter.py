import os
import re
from typing import Any, Dict, Optional

from fastapi import FastAPI

from faster_sam.cloudformation import CloudformationTemplate, NodeType
from faster_sam.envs import Envs
from faster_sam.openapi import custom_openapi
from faster_sam.routing import APIRoute, QueueRoute, ScheduleRoute

ARN_PATTERN = r"^arn:aws:apigateway.*\${(\w+)\.Arn}/invocations$"


class GatewayLookupError(LookupError):
    """
    Raised when performing API Gateway lookup, usually when multiple gateways
    are available requiring an explicit target.
    """

    pass


class SAM:
    """
    Adapter class for FastAPI applications allowing map API routes defined
    on a CloudFormation template or OpenAPI file.

    Parameters
    ----------
    template_path : Optional[str]
        Path to the CloudFormation template file.

    Attributes
    ----------
    template : CloudformationTemplate
        Instance of CloudformationTemplate based on the provided template_path.
    """

    def __init__(self, template_path: Optional[str] = None) -> None:
        """
        Initializes the SAM object.
        """

        self.template = CloudformationTemplate(template_path)

    def configure_api(self, app: FastAPI, gateway_id: Optional[str] = None) -> None:
        """
        Configures the FastAPI application with routes based on one of
        the following template files: CloudFormation, OpenAPI.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance to be configured.
        gateway_id : Optional[str], optional
            Optional API Gateway resource ID defined on the CloudFormation
            template. When multiple API Gateways are defined on the template
            this argument is required to identify which gateway is being mapped.

        Raises
        ------
        GatewayLookupError
            Raised if multiple API Gateways are defined on the CloudFormation
            template and the gateway_id are not set.
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

        self.register_routes(app, routes, APIRoute)

    def configure_queues(
        self,
        app: FastAPI,
    ) -> None:
        """
        Configures the FastAPI application with routes based on queues defined
        in cloudformation template.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance to be configured.
        """
        routes = self.lambda_queue_mapper()

        self.register_routes(app, routes, QueueRoute)

    def configure_schedule(
        self,
        app: FastAPI,
    ) -> None:
        """
        Configures the FastAPI application with routes based on schedule defined
        in cloudformation template.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance to be configured.
        """
        routes = self.lambda_schedule_mapper()

        self.register_routes(app, routes, ScheduleRoute)

    def openapi_mapper(self, openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a route map extracted from the given OpenAPI schema.

        Notice that this is an OpenAPI schema used by AWS SAM to configure
        an API Gateway, therefore it requires AWS extensions pointing to
        event consumers, most of the time Lambda Functions.

        e.g.

        >>> # The OpenAPI input schema is omitting information for brevity
        >>> schema = '''
        ... paths:
        ...   /health:
        ...     get:
        ...       x-amazon-apigateway-integration:
        ...          passthroughBehavior: when_no_match
        ...          httpMethod: POST
        ...          type: aws_proxy
        ...          uri:
        ...            Fn::Sub: "arn:aws:apigateway::lambda:path/2015-03-31/
        ...            functions/${HealthFunction.Arn}/invocations"
        ...          credentials: "arn:aws:iam:::role/apigateway-invoke-lambda-role"
        ... '''
        >>> SAM().openapi_mapper(schema)
        {"/health": {"get": {"handler": "src.handlers.health"}}}

        Parameters
        ----------
        openapi_schema : Dict[str, Any]
            OpenAPI schema dictionary.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing the routes.
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

    def lambda_queue_mapper(self) -> Dict[str, Any]:
        """
        Generate a route map extracted from the lambda functions that is a queue consumer
        using the name of the queue as path.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing the routes.
        """

        routes: Dict[str, Any] = {}

        for resource_id, function in self.template.functions.items():
            if "Events" not in function["Properties"]:
                continue

            events = self.template.find_nodes(function["Properties"]["Events"], NodeType.SQS_EVENT)

            for event in events.values():
                handler_path = self.template.lambda_handler(resource_id)
                resource_arn = event["Properties"]["Queue"]["Fn::GetAtt"]

                if isinstance(resource_arn, list):
                    resource_arn = resource_arn[0]

                resource_name = resource_arn.replace(".Arn", "")
                queue_name = self.template.queues[resource_name]["Properties"]["QueueName"]

                path = f"/{queue_name}"
                endpoint = {"POST": {"handler": handler_path}}

                routes.setdefault(path, {}).update(endpoint)

        return routes

    def lambda_schedule_mapper(self) -> Dict[str, Any]:
        """
        Generate a route map extracted from the lambda functions that is a schedule consumer
        using the name of the function name as path.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing the routes.
        """

        routes: Dict[str, Any] = {}

        for resource_id, function in self.template.functions.items():
            if "Events" not in function["Properties"]:
                continue

            events = self.template.find_nodes(
                function["Properties"]["Events"], NodeType.SCHEDULER_EVENT
            )

            if not events:
                continue

            function_name = function["Properties"]["FunctionName"].replace("_", "-")
            handler_path = self.template.lambda_handler(resource_id)

            path = f"/{function_name}"
            endpoint = {"POST": {"handler": handler_path}}

            routes.setdefault(path, {}).update(endpoint)

        return routes

    def lambda_mapper(self, gateway_id: Optional[str]) -> Dict[str, Any]:
        """
        Generate a route map extracted from the lambda functions schema
        corresponding to the given gateway id.

        Parameters
        ----------
        gateway_id : Optional[str]
            Optional gateway id to filter the routes for a specific API Gateway.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing the routes.
        """

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

    def register_routes(self, app: FastAPI, routes: Dict[str, Any], class_override=None) -> None:
        """
        Registers FastAPI routes based on the provided route map into the
        given FastAPI application.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance.
        routes : Dict[str, Any]
            Dictionary containing FastAPI routes.
        """

        for path, methods in routes.items():
            for method, config in methods.items():
                app.router.add_api_route(
                    path,
                    config["handler"],
                    methods=[method],
                    route_class_override=class_override,
                )

    def load_envs(self):
        env = Envs(self.template)
        queues = {}

        for env_key, env_value in env.envs.items():
            env.set_queue_envs(env_key, env_value, queues)
            env.filter_envs(env_key, env_value)
            env.mapper_variables(env_key, env_value)

        for env_key, env_value in env.envs.items():
            os.environ[env_key] = env_value
