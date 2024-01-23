import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass
class Credentials:
    access_key: Optional[str] = field(default=None)
    secret_access_key: Optional[str] = field(default=None)
    session_token: Optional[str] = field(default=None)
    role_arn: Optional[str] = field(default=None)
    web_identity_token: Optional[str] = field(default=None)
    web_identity_callable: Optional[Callable[[], Optional[str]]] = field(default=None)
    role_session_name: Optional[str] = field(default=None)
    region: Optional[str] = field(default=None)


class LambdaClient:
    """
    AWS Lambda client for handling session lifecycle.

    Parameters
    ----------
    credentials : Credentials
        The AWS credentials used to authenticate with the Lambda service.
    session_duration : int, optional
        The duration (in seconds) for which the assumed role credentials should be valid.
        Defaults to 900 seconds (15 minutes).
    expiration_threshold : int, optional
        The expiration threshold (in seconds) to check if the credentials are considered expired.
        Defaults to 2 seconds.

    Runtime Attributes
    ----------
    _expires_at : Optional[datetime]
        The timestamp when the assumed role credentials expire.
    _client : Optional[BaseClient]
        The AWS Lambda client instance.


    e.g

    This example get a lambda client.

    >>> lambda_client = LambdaClient(self.credentials)
    >>> ...
    >>> if lambda_Client.expired:
    >>>    lambda_client.refresh()
    >>> ...
    >>> client = lambda_client.client
    """

    def __init__(
        self,
        credentials: Credentials,
        session_duration: int = 900,
        expiration_threshold: int = 2,
    ) -> None:
        """
        Initializes the LambdaClient.
        """
        self.credentials = credentials
        self.session_duration = session_duration
        self.expiration_threshold = timedelta(seconds=expiration_threshold)
        self._expires_at = None
        self._client = None

    @property
    def client(self) -> BaseClient:
        """
        Returns the AWS Lambda client instance, creating one if not already available.

        Returns
        -------
        Client
            The AWS Lambda client instance.
        """
        if self._client is None:
            self.set_client()

        return self._client  # type: ignore

    @property
    def expired(self) -> bool:
        """
        Checks if the assumed role credentials are expired.

        Returns
        -------
        bool
            True if the credentials are expired, False otherwise.
        """
        if self._expires_at is None:
            return False

        now = datetime.now(tz=timezone.utc)
        remaining = self._expires_at - now

        return remaining > self.expiration_threshold

    def assume_role(self) -> Credentials:
        """
        Assumes the specified role using web identity token and returns
        the assumed role temporary credentials.

        Returns
        -------
        Credentials
            The assumed role temporary credentials.
        """
        sts = boto3.client("sts")

        if callable(self.credentials.web_identity_callable):
            function = sts.assume_role_with_web_identity
            web_identity = self.credentials.web_identity_callable()
        elif self.credentials.web_identity_token is not None:
            function = sts.assume_role_with_web_identity
            web_identity = self.credentials.web_identity_token
        else:
            raise NotImplementedError()

        response = function(
            DurationSeconds=self.session_duration,
            RoleArn=self.credentials.role_arn,
            RoleSessionName=self.credentials.role_session_name,
            WebIdentityToken=web_identity,
        )

        expires = response["Credentials"]["Expiration"]
        self._expires_at = expires.astimezone(tz=timezone.utc)

        return Credentials(
            access_key=response["Credentials"]["AccessKeyId"],
            secret_access_key=response["Credentials"]["SecretAccessKey"],
            session_token=response["Credentials"]["SessionToken"],
            region=self.credentials.region,
        )

    def set_client(self) -> None:
        """
        Sets the AWS Lambda client with the provided credentials.

        Returns
        -------
        None
        """
        credentials = self.credentials

        if self.credentials.role_arn is not None:
            credentials = self.assume_role()

        self._client = boto3.client(
            "lambda",
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_access_key,
            aws_session_token=credentials.session_token,
            region_name=credentials.region,
        )

    def refresh(self):
        """
        Refreshes the AWS Lambda client by re-setting the credentials if needs
        and instantiating a new AWS Lambda client.

        Returns
        -------
        None
        """
        self.set_client()


class LambdaAuthorizerMiddleware(BaseHTTPMiddleware):
    """
    Invoke Lambda function at AWS to authorize API requests.

    e.g

    This example apply the middleware to authorize an app.

    >>> app = FastAPI()
    >>> app.add_middleware(LambdaAuthorizer, arn="arn:aws:lambda:region:id:function:name")

    Parameters
    ----------
        app : ASGIApp
            Application instance the middleware is being registered to.
        arn : str
            The amazon resource name for the Lambda will be invoked.
        client: BaseClient
            Client Lambda object
    """

    def __init__(
        self,
        app: ASGIApp,
        lambda_function: str,
        credentials: Credentials = Credentials(),
    ) -> None:
        """
        Initializes the LambdaAuthorizer.
        """
        super().__init__(app, self.dispatch)
        self.lambda_function = lambda_function
        self._lambda_client = None
        self.credentials = credentials

    @property
    def client(self) -> BaseClient:
        """
        Returns the Lambda client instance, creating one if not already available.
        If the existing client has expired, it will be refreshed before returning.

        Returns
        -------
        BaseClient
            The Lambda client instance.
        """
        if self._lambda_client is None:
            self._lambda_client = LambdaClient(self.credentials)

        if self._lambda_client.expired:
            self._lambda_client.refresh()

        return self._lambda_client.client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Authorize or deny a request based on Authorization field.

        Parameters
        ----------
        request : Request
            The incoming request.
        call_next : RequestResponseEndpoint
            Next middleware or endpoint on the execution stack

        Returns
        -------
        Response
            The response generated by the middleware.
        """

        payload = self.invoke_lambda(request)

        if payload and payload["policyDocument"]["Statement"][0]["Effect"] == "Allow":
            return await call_next(request)

        content = {"message": "Unauthorized"}
        status_code = HTTPStatus.UNAUTHORIZED

        if payload is None:
            content = {"message": "Something went wrong. Try again"}
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR

        return Response(content=json.dumps(content), status_code=status_code.value)

    def invoke_lambda(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Invoke a Lambda using arn from AWS.

        Parameters
        ----------
        request : Request
            The incoming request.

        Returns
        -------
        Response
            The response payload generated by AWS Lambda invoked.
        """
        input_payload = self.build_event(request)

        try:
            response = self.client.invoke(
                FunctionName=self.lambda_function,
                Payload=json.dumps(input_payload),
            )
        except Exception as error:
            logger.exception(error)
            return None

        data = response["Payload"].read()

        output_payload = json.loads(data)

        return output_payload

    def build_event(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Convert request object to an AWS API Gateway event.

        Parameters
        ----------
        request : Request
            The incoming request.

        Returns
        -------
        event: Dict
            Event in AWS API Gateway format.
        """
        event = {
            "type": "REQUEST",
            "methodArn": f"arn:aws:execute-api:region:xxxx:/{request.method}/{request.url.path}",  # noqa
            "resource": request.url.path,
            "path": request.url.path,
            "httpMethod": request.method,
            "headers": dict(request.headers),
            "queryStringParameters": dict(request.query_params),
            "pathParameters": request.path_params,
            "requestContext": {
                "path": request.url.path,
                "stage": request.app.version,
                "requestId": str(uuid4()),
                "identity": {
                    "userAgent": request.headers.get("user-agent"),
                    "sourceIp": getattr(request.client, "host", None),
                },
                "httpMethod": request.method,
                "domainName": request.url.hostname,
                "apiId": request.scope.get("http_version"),
                "accountId": "xxxx",
            },
        }
        return event
