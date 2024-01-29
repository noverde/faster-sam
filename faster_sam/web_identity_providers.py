import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Provider(Enum):
    """
    Enumeration of identity providers.

    Providers:
        GCP: Google Cloud Platform identity provider.
    """

    GCP = "gcp"


class ProviderInterface(ABC):
    """
    Interface for identity providers.

    This abstract base class defines an interface for identity providers
    to implement. Subclasses must implement the `get_token` method to provide
    functionality for retrieving identity tokens.
    """

    @abstractmethod
    def get_token(self) -> Optional[str]:
        """
        Get the identity token.

        This method should be implemented by subclasses to retrieve the
        identity token from the respective identity provider.

        Returns
        -------
        token : str or None
            The identity token if available, else None.
        """
        pass  # pragma: no cover


class GCPProvider(ProviderInterface):
    """
    Requests identity information from the metadata server.

    e.g

    This example retrieves an identity token in the JWT format.

    >>> provider = GCPProvider()
    >>> provider.get_token()

    Environment Variables
    ---------------------
    WEB_IDENTITY_AUDIENCE : str
        The unique URI agreed upon by both the instance and the
        system verifying the instance's identity. For example, the audience
        could be a URL for the connection between the two systems.
    WEB_IDENTITY_FORMAT : str
        The optional parameter that specifies whether the project and
        instance details are included in the payload. Specify `full` to
        include this information in the payload or standard to omit the
        information from the payload. The default value is `standard`.
    WEB_IDENTITY_LICENSES : bool
        An optional parameter that specifies whether license
        codes for images associated with this instance are included in the
        payload. Specify TRUE to include this information or FALSE to omit
        this information from the payload. The default value is FALSE.
        Has no effect unless format is `full`.
    """

    def __init__(self) -> None:
        """
        Initializes the GCPProvider.
        """
        audience = os.getenv("WEB_IDENTITY_AUDIENCE", "")
        format = os.getenv("WEB_IDENTITY_FORMAT", "standard")
        licenses = os.getenv("WEB_IDENTITY_LICENSES", "FALSE")

        self._url = (
            "http://metadata.google.internal/computemetadata/v1/"
            "instance/service-accounts/default/identity?"
            f"audience={audience}&format={format}&licenses={licenses}"
        )

        self._headers = {"Metadata-Flavor": "Google"}

    def get_token(self) -> Optional[str]:
        """
        Get a JSON Web Token (JWT) signed by Google using the RS256 algorithm
        containing the identity information of the requester.

        Returns
        ----------
        token : str or None
            The identity token if available, else None.
        """

        response = requests.get(self._url, headers=self._headers)

        logger.debug(f"Response [{response.status_code}]: {response.text}")

        if not response.ok:
            return None

        return response.text


def factory(provider: str) -> ProviderInterface:
    """
    Factory function for creating identity provider instances.

    This function takes a provider name as input and returns an instance
    of the corresponding identity provider class.

    e.g

    This example get an instance of provider.

    >>> provider = factory(provider="gcp")
    >>> token = provider.get_token()

    Parameters
    ----------
    provider : str
        The name of the identity provider.

    Returns
    -------
    provider : ProviderInterface
        An instance of the identity provider class
        corresponding to the specified provider name.
    """
    providers = {Provider.GCP: GCPProvider}
    key = Provider(provider)

    return providers[key]()
