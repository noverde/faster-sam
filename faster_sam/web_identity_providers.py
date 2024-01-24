import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Provider(Enum):
    GCP = "gcp"


class ProviderInterface(ABC):
    @abstractmethod
    def get_token(self) -> Optional[str]:
        pass  # pragma: no cover


class GCPProvider(ProviderInterface):
    def __init__(self) -> None:
        audience = os.getenv("WEB_IDENTITY_AUDIENCE", "")
        format = os.getenv("WEB_IDENTITY_FORMAT", "standard")
        licenses = "WEB_IDENTITY_LICENSES" in os.environ

        self._url = (
            "http://metadata.google.internal/computemetadata/v1/"
            "instance/service-accounts/default/identity?"
            f"audience={audience}&format={format}&licenses={licenses}"
        )

        self._headers = {"Metadata-Flavor": "Google"}

    def get_token(self) -> Optional[str]:
        response = requests.get(self._url, headers=self._headers)

        logger.debug(f"Response [{response.status_code}]: {response.text}")

        if not response.ok:
            return None

        return response.text


def factory(provider: str) -> ProviderInterface:
    providers = {Provider.GCP: GCPProvider}
    key = Provider(provider)

    return providers[key]()
