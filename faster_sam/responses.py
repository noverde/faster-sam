from typing import Any, Dict
from fastapi import Response


class ApiGatewayResponse(Response):
    """
    Represents an API Gateway HTTP response.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initializes the ApiGatewayResponse.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary containing the response data.
        """

        super().__init__(
            content=data["body"],
            status_code=data["statusCode"],
            headers=data.get("headers"),
            media_type=data.get("headers", {}).get("Content-Type"),
        )


class SQSResponse(Response):
    """
    Represents an API Gateway HTTP response.
    """

    def __init__(self, body, status_code):
        """
        Initializes the ApiGatewayResponse.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary containing the response data.
        """

        super().__init__(
            content=body,
            status_code=status_code,
        )
